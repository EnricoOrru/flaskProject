import datetime

from flask import Flask, render_template, request
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
    tumbleweedBool = request.form.get('tumbleweed')
    tumbleweedPriority = request.form.get('tumbleweedCombo')
    washingmachineBool = request.form.get('washing_machine')
    washingmachinePriority = request.form.get('washingMachineCombo')

    energy, graph = SolarProduction.main(postcode, nSolar, orientation, angle, date, dishwasherBool, dishwasherPriority, tumbleweedBool,
                         tumbleweedPriority, washingmachineBool, washingmachinePriority)

    return render_template('ResultPage.html', encoded_image=graph)

@app.route('/update_slider', methods=['POST'])
def update_slider():
    slider_value = int(request.form['slider_value'])
    print(slider_value)
    return 'OK'

if __name__ == '__main__':
    app.run()
