import requests
import json
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy_utils import database_exists, create_database

######### change these to env vars or whatever is best practice
postgres_user='postgres'
postgres_password='postgres'
database='finance'

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

params = {
    'interval': '1d',
    'range': 'ytd',
}

etf_list=['xle','xlf','xlu','xli','xlk','xlv','xly','xlp','xlb']

# Getting data from Yahoo Finance API and reformatting slightly 
def get_data(tickers):
    data=pd.DataFrame()
    for ticker in tickers:
        r=requests.get(f'https://query1.finance.yahoo.com/v8/finance/chart/{ticker}', params=params, headers=headers)
        response=json.loads(r.text)
        prices=pd.json_normalize(response['chart']['result'][0]['indicators']['quote'][0]).explode(['high','low','close','open','volume']).reset_index(drop=True)
        prices['ticker']=ticker
        # TODO: dont parse this more than once 
        timestamps=response['chart']['result'][0]['timestamp']
        ticker_data=pd.concat([pd.Series(timestamps, name='date'), prices], axis=1)
        data=pd.concat([data, ticker_data]).reset_index(drop=True)
    data['key']=data['ticker'] + data['date'].astype(str)
    data['date']=pd.to_datetime(data['date'],unit='s')
    data=data.sort_values(by=['date','ticker']).reset_index(drop=True)
    return data

# Load data to postgres  
def load_to_db(df):
    eng = create_engine(f"postgresql://{postgres_user}:{postgres_password}@localhost/{database}")
    if not database_exists(eng.url):
        create_database(eng.url)

    df.to_sql(name="dashboard", con=eng, if_exists='append', index=False)

    remove_dupes_query="""
    DELETE FROM dashboard dupes 
    USING dashboard distinct_rows 
    WHERE dupes.id < distinct_rows.id AND dupes.key = distinct_rows.key
    """
    #eng.execute(remove_dupes_query)
    print('finished loading data into postgres')

if __name__=='__main__':
    new_data=get_data(etf_list)
    load_to_db(new_data)
