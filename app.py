import datetime

import ipdb
import matplotlib.pyplot as plt
from flask import Flask, render_template, request
from flask_bootstrap import Bootstrap
import SolarProduction

app = Flask(__name__)


@app.route('/')
def index():
    return render_template('Frontpage.html')


@app.route('/submit', methods=['POST'])
def submit():
    postcode = request.form.get('postcode')
    nSolar = int(request.form.get('num_panels'))
    orientation = float(request.form.get('orientation'))
    angle = float(request.form.get('angle'))
    date = datetime.datetime.fromisoformat(request.form.get('date'))
    dishwasherBool = request.form.get('dishwasher')
    dishwasherPriority = request.form.get('dishwasherCombo')
    tvBool = request.form.get('tv')
    tvPriority = request.form.get('tvCombo')
    washingmachineBool = request.form.get('washing_machine')
    washingmachinePriority = request.form.get('washingMachineCombo')

    today = datetime.datetime.today()
    if date.date() == today.date():
        return render_template('ErrorPage.html')

    energy, graph, resulted_production = SolarProduction.main(postcode, nSolar, orientation, angle, date, dishwasherBool
                                                              , dishwasherPriority, tvBool, tvPriority,
                                                              washingmachineBool, washingmachinePriority)

    SolarProduction.plot_graph(resulted_production, SolarProduction.list_of_consumption_dishwasher_global,
                               SolarProduction.list_of_consumption_washingmachine_global,
                               SolarProduction.list_of_consumption_tv_global, "Resulted Production",
                               50, 50, 50)
    resulted_production_image = SolarProduction.graph_to_image()
    return render_template('ResultPage.html', encoded_image=graph,
                           max_dishwasher=SolarProduction.max_hour_dishwasher_global,
                           max_tv=SolarProduction.max_hour_tv_global,
                           max_washingmachine=SolarProduction.max_hour_washingmachine_global,
                           resulted_graph=resulted_production_image, energy= energy)


@app.route('/update_slider', methods=['POST'])
def update_slider():
    slider_dishwasher = int(request.form['slider_dishwasher'])
    slider_washingmachine = int(request.form['slider_washingmachine'])
    slider_tv = int(request.form['slider_tv'])

    SolarProduction.plot_graph(SolarProduction.list_of_production_origin_global,
                               SolarProduction.list_of_consumption_dishwasher_global,
                               SolarProduction.list_of_consumption_washingmachine_global,
                               SolarProduction.list_of_consumption_tv_global, SolarProduction.title_global,
                               slider_dishwasher, slider_washingmachine, slider_tv)
    graph = SolarProduction.graph_to_image()
    return graph


@app.route('/update_resulting_graph', methods=['POST'])
def update_resulting_graph():
    slider_dishwasher = int(request.form['slider_dishwasher'])
    slider_washingmachine = int(request.form['slider_washingmachine'])
    slider_tv = int(request.form['slider_tv'])

    list_of_production_after_consumption = SolarProduction.get_resulting_production(SolarProduction.list_of_production_origin_global,
                                                                                    SolarProduction.list_of_consumption_dishwasher_global,
                                                                                    SolarProduction.list_of_consumption_washingmachine_global,
                                                                                    SolarProduction.list_of_consumption_tv_global,
                                                                                    slider_dishwasher,
                                                                                    slider_washingmachine,
                                                                                    slider_tv)

    SolarProduction.plot_graph(list_of_production_after_consumption, SolarProduction.list_of_consumption_dishwasher_global,
                               SolarProduction.list_of_consumption_washingmachine_global,
                               SolarProduction.list_of_consumption_tv_global,
                               "Production After New Consumption",
                               50, 50, 50)
    graph = SolarProduction.graph_to_image()
    return graph


if __name__ == '__main__':
    app.run()
