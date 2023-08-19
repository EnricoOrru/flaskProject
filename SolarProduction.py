import io
import pdb
from datetime import datetime
import datetime as dt
from statistics import mean
import base64
import ipdb
import numpy as np
import pandas as pd
import pvlib
import pytz
import requests
from geopy import Nominatim
from matplotlib import pyplot as plt
from pvlib.modelchain import ModelChain
from pvlib.location import Location
from pvlib.pvsystem import PVSystem
from pvlib.temperature import TEMPERATURE_MODEL_PARAMETERS
import matplotlib.dates as mdates
import time as t

from timezonefinder import TimezoneFinder


def get_location(postcode):
    latitude, longitude = get_lat_lng_from_postcode(postcode)
    timezone = calculateTimezoneFromLocation(latitude, longitude)
    # latitude = 56.652163
    # longitude = -2.907930
    # timezone = "Europe/London"
    location = Location(latitude, longitude, timezone)
    return location


def set_up_system(nSolar, orientation, angle):
    # find module and inverter through the database
    sandia_modules = pvlib.pvsystem.retrieve_sam('SandiaMod')
    cec_inverters = pvlib.pvsystem.retrieve_sam('CECinverter')

    # for modules in sandia_modules.columns.tolist():
    #     print(modules)

    module = sandia_modules['SunPower_SPR_315E_WHT__2007__E__']
    inverter = cec_inverters['SMA_America__SB2000HFUS_30__240V_']

    temperature_parameters = TEMPERATURE_MODEL_PARAMETERS['sapm']['open_rack_glass_glass']

    # modules_per_string number of modules connected in series with a string
    # strings_per_inverter is the number of strings connected in parallel to an inverter
    surface_tilt = angle
    surface_azimuth = orientation
    system = PVSystem(surface_tilt=surface_tilt,
                      surface_azimuth=surface_azimuth,
                      module_parameters=module,
                      inverter_parameters=inverter,
                      temperature_model_parameters=temperature_parameters,
                      modules_per_string=nSolar,
                      strings_per_inverter=1)
    return system


def set_up_modelchain(system, location):
    # The system rapresents the PV system and the location the physical location of our system on the planet
    modelchain = ModelChain(system, location, clearsky_model='ineichen')
    return modelchain


def set_up_timerange(location, start, end):
    # create the time for which I want the weather information
    time_range = pd.date_range(start=start,
                               end=end,
                               freq='1h',
                               tz=location.tz)
    return time_range


def set_up_clearsky(location, time_range):
    # retrieve weather information about the time range
    clear_sky = location.get_clearsky(time_range)
    return clear_sky


def main(postcode, nSolar, orientation, angle, date, dishwasherBool, dishwasherPriority, tumbleweedBool,
         tumbleweedPriority, washingmachineBool, washingmachinePriority):

    max_hour_dishwasher = 50
    max_hour_washingmachine = 50
    max_hour_tumbleweed = 50

    dictionary_of_priorities = {
        "dishwasher": [dishwasherBool, dishwasherPriority],
        "tumbleweed": [tumbleweedBool, tumbleweedPriority],
        "washingmachine": [washingmachineBool, washingmachinePriority]
    }

    priority_order = ["high", "medium", "low"]

    def custom_priority_sort(item):
        try:
            return priority_order.index(item[1][1])
        except ValueError:
            return len(priority_order)

    sorted_priorities = sorted(dictionary_of_priorities.items(), key=custom_priority_sort)

    sorted_dictionary = dict(sorted_priorities)

    location = get_location(postcode)
    system = set_up_system(nSolar, orientation, angle)
    modelchain = set_up_modelchain(system, location)
    energy, list_of_production = calculate_actual_solar_energy(date, replace_day(date, date.day + 1), modelchain)

    # fare priorità
    list_of_production_origin = list_of_production

    list_of_consumption_dishwasher = [1.92, 79.93, 307.88, 6.52, 6.1, 6.47, 7.17, 7.23, 7.68, 162.3, 285.72, 9.22]
    list_of_consumption_tumbleweed = [1.92, 79.93, 307.88, 6.52, 6.1, 6.47, 7.17, 7.23, 7.68, 162.3, 285.72, 9.22]
    list_of_consumption_washingmachine = [0, 1, 0.18, 13.05, 20.62, 18.12, 11.62, 11.88, 82.38, 358.22, 1, 0]

    for device, (booleanCheck, priority) in sorted_dictionary.items():
        if booleanCheck == "on" and device == "dishwasher":
            max_hour_dishwasher, list_of_production = calculate_optimal_time(list_of_consumption_dishwasher,
                                                                             list_of_production)
        if booleanCheck == "on" and device == "tumbleweed":
            max_hour_tumbleweed, list_of_production = calculate_optimal_time(list_of_consumption_tumbleweed, list_of_production)

        if booleanCheck == "on" and device == "washingmachine":
            max_hour_washingmachine, list_of_production = calculate_optimal_time(list_of_consumption_washingmachine,list_of_production)


    # max_hour_dishwasher, list_of_production = calculate_optimal_time(list_of_consumption_dishwasher, list_of_production)
    # max_hour_tumbleweed, list_of_production = calculate_optimal_time(list_of_consumption_tumbleweed, list_of_production)
    # max_hour_washingmachine, list_of_production = calculate_optimal_time(list_of_consumption_washingmachine,
    #                                                                      list_of_production)

    plot_graph(list_of_production_origin, list_of_consumption_dishwasher, list_of_consumption_washingmachine,
                     list_of_consumption_tumbleweed, "List of Production After Consumption"+ str(date), max_hour_dishwasher,
                     max_hour_washingmachine, max_hour_tumbleweed)
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png')
    plt.close()
    buffer.seek(0)
    encoded_image = base64.b64encode(buffer.read()).decode('utf-8')

    return energy, encoded_image


def calculate_actual_solar_energy(initial_date, final_date, modelchain):
    hour_difference = int(calculate_difference_between_times(initial_date, final_date))
    list_of_cloudiness = []
    if check_days_difference(initial_date, modelchain.location) >= -2 and check_days_difference(initial_date,
                                                                                                modelchain.location) < 0:
        list_of_cloudiness = callToWeatherAPIFuture(initial_date)
    if check_days_difference(initial_date, modelchain.location) < 365 and len(list_of_cloudiness) == 0:
        list_of_cloudiness = callToWeatherAPIPast(initial_date, final_date)

    if check_days_difference(initial_date, modelchain.location) == 0 or check_days_difference(initial_date,
                                                                                              modelchain.location) < -2 or \
            check_days_difference(initial_date, modelchain.location) >= 365:
        return 0, 0

    if final_date.day == initial_date.day:
        final_date = replace_hour(final_date, addHours(initial_date, 1).hour)
    else:
        final_date = replace_day(final_date, initial_date.day)
        final_date = replace_hour(final_date, addHours(initial_date, 1).hour)

    energy = 0
    time_range = set_up_timerange(modelchain.location, initial_date, final_date)
    clear_sky = set_up_clearsky(modelchain.location, time_range)
    modelchain.run_model(clear_sky)
    cloud_cover = (1 - (get_dissipation_value(list_of_cloudiness[0]) / 100))
    energy += modelchain.results.ac.values[0] * cloud_cover
    list_of_cloudiness.pop(0)

    list = []
    list.append(modelchain.results.ac.values[0])
    initial_date = addHours(initial_date, 1)
    final_date = addHours(final_date, 1)
    for i in range(hour_difference - 1):
        time_range = set_up_timerange(modelchain.location, initial_date, final_date)
        clear_sky = set_up_clearsky(modelchain.location, time_range)
        modelchain.run_model(clear_sky)
        cloud_cover = (1 - (get_dissipation_value(list_of_cloudiness[i]) / 100))
        energy += modelchain.results.ac.values[0] * cloud_cover
        list.append(modelchain.results.ac.values[0])
        initial_date = addHours(initial_date, 1)
        final_date = addHours(final_date, 1)
    return energy, list


def calculate_difference_between_times(datetime1, datetime2):
    diff = datetime2 - datetime1
    hours = diff.total_seconds() / 3600
    return hours


# def calculate_difference_between_times(initial_date: datetime, final_date: datetime):
#     initial_hour = initial_date.hour
#     final_hour = final_date.hour
#     hour_difference = final_hour - initial_hour
#     return hour_difference


# def callToWeatherAPI(initial_date: datetime, final_date: datetime):
#     location = get_location()
#     inital_date_utc = convert_to_utc(initial_date, location.tz)
#     final_date_utc = convert_to_utc(final_date, location.tz)
#     initial_time = str(inital_date_utc).replace(' ', ':')[:-6]
#     final_time = str(final_date_utc).replace(' ', ':')[:-6]
#     latitude = str(location.latitude)
#     longitude = str(location.longitude)
#     url = 'https://api.weatherbit.io/v2.0/history/hourly?lat='+latitude+'&lon='+longitude+'&' \
#           'start_date='+initial_time+'&end_date='+final_time+'&tz=utc&key=692afbc7b1184804b4598a5998ddf629'
#     #ipdb.set_trace()
#     # url = 'https://api.weatherbit.io/v2.0/history/hourly?lat=56.64482956171486&lon=-2.888728934975756&' \
#     #        'start_date=2023-05-12:00&end_date=2023-05-13:00&tz=local&key=692afbc7b1184804b4598a5998ddf629'
#     response = requests.get(url)
#
#     if response.status_code == 200:
#         data = response.json()
#         list_of_cloudiness = []
#         for entry in data['data']:
#             clouds = entry['clouds']
#             list_of_cloudiness.append(clouds)
#         return list_of_cloudiness
#     else:
#         print('Error:', response.status_code)


def callToWeatherAPIPast(initial_date: datetime, final_date: datetime):
    location = get_location("DD12HF")
    inital_time = str(int(convert_to_unix_time(initial_date, location)))
    final_time = str(int(convert_to_unix_time(final_date, location)))
    latitude = str(round(location.latitude, 5))
    longitude = str(round(location.longitude, 5))
    url = 'https://history.openweathermap.org/data/2.5/history/city?lat=' + latitude + '&lon=' + longitude \
          + '&type=hour&start=' + inital_time + '&end=' + final_time + '&appid=eb1b77df1c8a2ea0a4b2b4aea35e80e5'
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        list_of_cloudiness = []
        for data_point in data['list']:
            list_of_cloudiness.append(data_point['clouds']['all'])
        return list_of_cloudiness
    else:
        print('Error:', response.status_code)


def callToWeatherAPIFuture(desired_local_start_time):
    location = get_location("DD12HF")
    latitude = str(round(location.latitude, 5))
    longitude = str(round(location.longitude, 5))
    url = "https://pro.openweathermap.org/data/2.5/forecast/hourly?lat=" + latitude + "&lon=" + longitude + "&appid=eb1b77df1c8a2ea0a4b2b4aea35e80e5"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        unix_times = [entry['dt'] for entry in data['list']]
        desidered_time = unix_times[0]
        for time in unix_times:
            time_in_utc = unix_timestamp_to_utc(time)
            time_localized = convert_utc_to_timezone(time_in_utc, calculateTimezoneFromLocation(location))
            if (
                    time_localized.day == desired_local_start_time.day and time_localized.hour == desired_local_start_time.hour):
                desidered_time = time

        clouds_info = []
        for entry in data['list']:
            if entry['dt'] >= desidered_time:
                clouds_info.append(entry['clouds']['all'])

            if len(clouds_info) >= 24:
                break
        if len(clouds_info) == 0:
            for entry in data['list']:
                clouds_info.append(entry['clouds']['all'])

                if len(clouds_info) >= 24:
                    break
        return clouds_info

    else:
        print('Error:', response.status_code)


def convert_to_unix_time(date: datetime, location):
    tz = location.tz
    current_timezone = pytz.timezone(tz)
    utc_time = current_timezone.localize(date).astimezone(pytz.utc)
    unix_time = utc_time.timestamp()
    return unix_time


def replace_hour(dateToChange: datetime, hourToSwap):
    dateToReturn = dateToChange.replace(hour=hourToSwap)
    return dateToReturn


def replace_day(dateToChange: datetime, dayToSwap):
    dateToReturn = dateToChange.replace(day=dayToSwap)
    return dateToReturn


def addHours(input_date: datetime, hours):
    new_date = input_date + dt.timedelta(hours=hours)
    return new_date


def get_dissipation_value(cloudiness):
    value = (25 * cloudiness) / 100
    return value


def convert_to_utc(dt, timezone_str):
    # Get the time zone object corresponding to the given timezone_str
    timezone = pytz.timezone(timezone_str)

    # Localize the input datetime to the specified timezone
    localized_datetime = timezone.localize(dt)

    # Convert the localized datetime to UTC, but keep the hour value unchanged
    utc_datetime = localized_datetime.astimezone(pytz.UTC).replace(tzinfo=None)

    return utc_datetime


def plot_graph(list_of_production, dishwasher, washingmachine, tumbleweed, title, max_hour_dishwasher,
               max_hour_washingmachine,
               max_hour_tumbleweed):
    hours = list(range(24))
    plt.figure()
    dishwasher = shrink_list_by_number_and_average(dishwasher)
    washingmachine = shrink_list_by_number_and_average(washingmachine)
    tumbleweed = shrink_list_by_number_and_average(tumbleweed)
    if max_hour_dishwasher != 50:
        dishwasher = [0] * (max_hour_dishwasher + 1) + dishwasher + [0] * (23 - max_hour_dishwasher - len(dishwasher))
    if max_hour_washingmachine != 50:
        washingmachine = [0] * (max_hour_washingmachine + 1) + washingmachine + [0] * (
                23 - max_hour_washingmachine - len(washingmachine))
    if max_hour_tumbleweed != 50:
        tumbleweed = [0] * (max_hour_tumbleweed + 1) + tumbleweed + [0] * (23 - max_hour_tumbleweed - len(tumbleweed))
    plt.plot(hours, list_of_production, label='Curve Of Production')
    if max_hour_dishwasher != 50:
        plt.plot(hours, dishwasher, label='Curve Of Consumption Dishwasher')
    if max_hour_washingmachine != 50:
        plt.plot(hours, washingmachine, label='Curve Of Consumption Washing Maching')
    if max_hour_tumbleweed != 50:
        plt.plot(hours, tumbleweed, label='Curve Of Consumption Tumbleweed')

    plt.xlabel('Hours')
    plt.ylabel('Watts')
    plt.title(title)

    plt.legend()
    plt.xticks(hours)
    if max_hour_tumbleweed != 50:
        plt.axvline(x=max_hour_tumbleweed, color='r', linestyle='--',
                    label=f'Start Hour of Dishwasher: {max_hour_tumbleweed}')
    if max_hour_dishwasher != 50:
        plt.axvline(x=max_hour_dishwasher, color='orange', linestyle='--',
                    label=f'Start Hour of Dishwasher: {max_hour_dishwasher}')
    if max_hour_washingmachine != 50:
        plt.axvline(x=max_hour_washingmachine, color='green', linestyle='--',
                    label=f'Start Hour of Dishwasher: {max_hour_washingmachine}')


def calculate_optimal_time(list_of_consumption, list_of_production):
    indexes_of_remaining_energy = dict()
    production_after_consumption_per_start_hour = dict()
    for startHour in range(0, 23):
        production_after_consumption = [x for x in list_of_production]
        for i in range(0, len(list_of_consumption), 6):
            production_after_consumption[int(i / 6) + startHour] -= mean(list_of_consumption[i:i + 6])
        indexes_of_remaining_energy[startHour] = production_after_consumption[startHour] + production_after_consumption[
            startHour + 1]
        production_after_consumption_per_start_hour[startHour] = production_after_consumption
    max_key = max(indexes_of_remaining_energy, key=indexes_of_remaining_energy.get)

    return max_key, production_after_consumption_per_start_hour[max_key]


def check_if_date_is_today(date, location):
    input_datetime = date.replace(tzinfo=pytz.UTC)
    desired_timezone = pytz.timezone(location.tz)
    input_datetime_in_timezone = input_datetime.astimezone(desired_timezone)

    today = datetime.now(desired_timezone).date()

    return input_datetime_in_timezone.date() == today


def check_days_difference(date, location):
    input_datetime = date.replace(tzinfo=pytz.UTC)
    desired_timezone = pytz.timezone(location.tz)
    input_datetime_in_timezone = input_datetime.astimezone(desired_timezone)

    current_datetime = datetime.now(desired_timezone)

    difference = current_datetime.date() - input_datetime_in_timezone.date()
    return difference.days


def unix_timestamp_to_utc(unix_timestamp):
    utc_datetime = dt.datetime.utcfromtimestamp(unix_timestamp)
    return utc_datetime


def convert_utc_to_timezone(utc_datetime, target_timezone):
    utc_timezone = pytz.timezone('UTC')
    target_timezone = pytz.timezone(target_timezone)
    localized_datetime = utc_datetime.replace(tzinfo=utc_timezone).astimezone(target_timezone)

    return localized_datetime


def calculateTimezoneFromLocation(latitude, longitude):
    timezone = TimezoneFinder().timezone_at(lat=latitude, lng=longitude)
    return timezone


def calculateLatitude(location):
    geolocator = Nominatim(user_agent="Myapp")
    location_info = geolocator.geocode(location)
    return location_info.latitude


def calculateLongitude(location):
    geolocator = Nominatim(user_agent="Myapp")
    location_info = geolocator.geocode(location)
    return location_info.longitude


def get_lat_lng_from_postcode(postcode):
    geolocator = Nominatim(user_agent="geoapi")

    location = geolocator.geocode(postcode)
    if location:
        latitude = location.latitude
        longitude = location.longitude
        return latitude, longitude
    else:
        print("Location not found for the provided postal code.")
        return None, None


def shrink_list_by_number_and_average(list):
    averages = []
    for i in range(0, len(list), 6):
        subset = list[i:i + 6]
        avg = sum(subset) / len(subset)
        averages.append(avg)
    return averages
