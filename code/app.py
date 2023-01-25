# for getting the data from Yahoo finance
import requests
import json
import pandas as pd
from sqlalchemy import create_engine
# for plots
import dateutil.relativedelta as rdelta
import plotly.express as px
from dash import Dash, html, dcc
import plotly.graph_objects as go

######### change these to env vars or whatever is best practice
postgres_user='root'
postgres_password='root'
database='database'
port='5432'
# host is the name of your postgres container
host='postgres_db'

params = {
    'interval': '1d',
    'range': 'ytd',
}

etf_list=['xle','xlf','xlu','xli','xlk','xlv','xly','xlp','xlb']

headers = {
    'authority': 'query1.finance.yahoo.com',
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'accept-language': 'en-US,en;q=0.5',
    'cache-control': 'max-age=0',
    'sec-ch-ua': '"Not?A_Brand";v="8", "Chromium";v="108", "Brave";v="108"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Linux"',
    'sec-fetch-dest': 'document',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'none',
    'sec-fetch-user': '?1',
    'sec-gpc': '1',
    'upgrade-insecure-requests': '1',
    'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
}

data=pd.DataFrame()
for ticker in etf_list:
    r=requests.get(f'https://query1.finance.yahoo.com/v8/finance/chart/{ticker}', params=params, headers=headers)
    response=json.loads(r.text)
    prices=pd.json_normalize(response['chart']['result'][0]['indicators']['quote'][0]).explode(['high','low','close','open','volume']).reset_index(drop=True)
    prices['ticker']=ticker
    # TODO: dont parse this more than once 
    timestamps=response['chart']['result'][0]['timestamp']
    ticker_data=pd.concat([pd.Series(timestamps, name='date'), prices], axis=1)
    data=pd.concat([data, ticker_data]).reset_index(drop=True)
data['date']=pd.to_datetime(data['date'],unit='s')
data=data.sort_values(by=['date','ticker']).reset_index(drop=True)

# loading to postgres
eng = create_engine(f"postgresql://{postgres_user}:{postgres_password}@{host}:{port}/{database}")
data.to_sql(name="dashboard", con=eng, if_exists='append', index=False)

remove_dupes_query="""
delete from dashboard where id in 
 (select id from 
    (select t.*, row_number() over (partition by to_char(date,'YYYY-MM-DD'), ticker) as seqnum from dashboard t 
    order by ticker, date desc) as t
     where seqnum>1);
"""
#eng.execute(remove_dupes_query)
print('finished loading data into postgres')

### Reformatting data and plotting
eng=create_engine(f"postgresql://{postgres_user}:{postgres_password}@{host}:{port}/{database}")
pg_data=pd.read_sql("select * from dashboard", con=eng)

# TODO: - put these into a csv/load into postgres as dim table - "preferred names"
ticker_names=pd.DataFrame.from_dict({'ticker':['xlb','xle','xlf','xli','xlk','xlp','xlu','xlv','xly'],\
 'full_names':['Materials (XLB)','Energy (XLE)','Financials (XLF)','Industrials (XLI)','Technology (XLK)',\
    'Consumer Staples (XLP)','Utilities (XLU)','Health Care (XLV)','Consumer Discretionary (XLY)']})


def weekly_returns(df):
    df=df.set_index('date')
    weekly_gb=df.groupby([df.index.month, df.index.isocalendar().week,'ticker'])['close'].agg(['first','last'])
    weekly_gb=weekly_gb.reset_index(0).rename(columns={'date':'month'}).reset_index(0).rename(columns={'date':'week'}).reset_index()
    weekly_gb=weekly_gb.sort_values(by=['month','week'], ascending=False)
    weekly_gb['returns'] = (weekly_gb['last'] / weekly_gb['first']) -1
    
    # Handles Mondays or holidays at beginning of the week for weekly returns chart
    # Checks if day is Monday or if all returns are zero for the week (possible that all returns can actually be zero but unlikely enough to leave it)
    if (pd.to_datetime('today').dayofweek == 0) | (all(0 == x for x in list(weekly_gb.iloc[0:9,:]['returns']))):
        weekly_gb=weekly_gb.loc[(weekly_gb['month']==(pd.to_datetime('today').month)) & (weekly_gb['week']==(pd.to_datetime('today').week -1 ))]
        last_monday=(pd.to_datetime('today') + rdelta.relativedelta(days=-1, weekday=rdelta.MO(-1))).strftime('%m/%d')
        last_friday=(pd.to_datetime('today') + rdelta.relativedelta(days=-1, weekday=rdelta.FR(-1))).strftime('%m/%d')
        daily_var=f'Returns from {last_monday}-{last_friday} (Current weeks returns will update with 2 days of data)'
    else:
        weekly_gb=weekly_gb.drop_duplicates(subset=['ticker','month'])
        daily_var='Current weeks returns'
    return weekly_gb,daily_var

def monthly_returns(df):
    df=df.set_index('date')
    monthly=df.groupby([df.index.year,df.index.month,'ticker'])['close'].agg(['first','last'])
    monthly=monthly.reset_index(0).rename(columns={'date':'date_year'}).reset_index(0).rename(columns={'date':'date_month'}).reset_index(0)
    monthly['monthly_return']=(monthly['last']/monthly['first'])-1
    monthly['date'] = pd.to_datetime(monthly['date_year'].astype(str)+monthly['date_month'].astype(str),format='%Y%m')
    return monthly

def ytd_returns(df):
    df=df.groupby([df['date'].dt.year,'ticker'])['close'].agg(['first','last']).reset_index()
    df['ytd_returns']=(df['last'] / df['first']) -1 
    df['color'] = ['Red' if i<0 else 'Green' for i in df['ytd_returns']]
    df=pd.merge(df, ticker_names, on='ticker',how='left')
    return df


weekly,daily_var=weekly_returns(pg_data)
monthly=monthly_returns(pg_data)
yearly=ytd_returns(pg_data)


ytd_fig=px.bar(yearly, x='full_names', y='ytd_returns', title='Year to Date Returns',
    labels={'ytd_returns':'','full_names':'ETF Name (Ticker)'}, hover_data=['ytd_returns'])
ytd_fig.update_traces(marker_color=yearly['color'])
ytd_fig.layout.yaxis.tickformat = ',.0%'

monthly_fig = go.Figure(data=[go.Table(
    header=dict(values=['Ticker','Month','Returns'],
                fill_color='darkslateblue',
                align='left',
                font_color='white'),
    cells=dict(values=[monthly.ticker, monthly.date.dt.strftime('%b-%y'), (monthly['monthly_return']*100).round(2).astype(str)+'%'],
               align='left'))
])
monthly_fig.update_layout(title_text='Monthly Returns')

weekly_fig=go.Figure(data=[go.Table(
    header=dict(values=['Ticker','Weekly Return'],
    fill_color='darkslateblue',
    font_color='white'),
    cells=dict(values=[weekly['ticker'], (weekly['returns']*100).round(2).astype(str)+'%'])
)])
weekly_fig.update_layout(title_text=f'Weekly Returns <br><sup>{daily_var}<sup>')


app = Dash(__name__)

app.layout = html.Div(children=[
    html.H1(children='Financial DASHboard'),

    html.Div(children='''
        Financial data for sector ETFs via Yahoo finance API, postgres, plotly, and dash    
    '''),

    dcc.Graph(
        id='ytd_graph',
        figure=ytd_fig
    ),

    dcc.Graph(
        id='mtd_graph',
        figure=monthly_fig
    ),

    dcc.Graph(
        id='wtd_graph',
        figure=weekly_fig
    )

])

if __name__ == '__main__':
    app.run_server(debug=True, host='0.0.0.0')

