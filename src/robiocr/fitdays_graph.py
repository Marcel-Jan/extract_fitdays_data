import sqlite3
import matplotlib.pyplot as plt
# import datetime

# Start date
start_date = "datetime.datetime(2021, 1, 1)"

# Read the health data from the database
conn = sqlite3.connect('/Volumes/backup/sqlite/fitdays_health_data.db', detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
c = conn.cursor()
query = """SELECT Measurement_datetime as "[timestamp]",
           Gewicht, Lichaamsvet
           FROM measurements 
           ORDER BY Measurement_datetime
        """

c.execute(query)
rows = c.fetchall()
print(rows)
conn.close()

# Create a graph with the Date on the x-axis and the Weight on the y-axis
dates = []
weights = []
fatpercent = []
for row in rows:
    print(row)
    dates.append(row[0])
    weights.append(row[1])
    fatpercent.append(row[2])

plt.figure(figsize=(1600/100, 600/100))

# Minimum y-axis value is 0
plt.ylim(min(weights) - 15, max(weights) + 5)
# plt.ylim(min(fatpercent) - 15, max(fatpercent) + 5)

# Show date on x axis as date
plt.gca().xaxis_date()

# Show x-axis labels only every 5 values
plt.gca().xaxis.set_major_locator(plt.MaxNLocator(5))
# plt.figure(figsize=(1600/100, 600/100))
plt.plot(dates, weights)
# plt.plot(dates, fatpercent)

plt.xlabel('Measurement_datetime')
plt.ylabel('Weight')
plt.title('Weight over time')
plt.show()

