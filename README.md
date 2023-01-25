Basic dashboard to show the year to date, month to date, and week to date performance of sector ETFs in the SP500. I made it because I wanted a quick way to monitor performance for different industries/time frames without having to stare at price charts all day. Next I'm planning on adding a searchbar with a list of ETFs the user can select and make the tables more interactive/sortable. 


![Screenshot 2023-01-25 at 4 26 45 PM](https://user-images.githubusercontent.com/87843056/214694954-f172dec0-906d-4ce1-8265-489d85e583cd.png)


QuickStart:
1. Clone this repo
2. Run docker-compose up in the fin_dashboard directory 
3. go to http://localhost:8050/
... 
profit? 

Technical Details: 

The data is pulled in from the yahoo finance api using python and then uploaded to the postgres docker container (this is convoluted for the current use case because the data is so small but was an excellent excuse to get more docker experience). Then the app.py script grabs the data from the postgres container and transforms it into yearly/monthly/weekly returns and plots it using dash/plotly.  
