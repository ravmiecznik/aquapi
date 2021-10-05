#!/usr/bin/python3 -u
import http
import json
import os
import time
from datetime import datetime

import ph_controller
from ph_controller import CSVParser
import plotly.express as px
import requests
from flask import Flask, request, render_template, abort
from pandas import DataFrame
from plotly.subplots import make_subplots

try:
    aquapi_address = "http://188.122.24.160:5000"
    requests.get(f'{aquapi_address}', timeout=20)
except requests.exceptions.ConnectionError:
    aquapi_address = "http://192.168.55.250:5000"

app = Flask(__name__, template_folder="resources")
this_path = os.path.dirname(__file__)
csv_log_path = 'log.csv'


log_data = None

def timestamp_to_datetime(timestap):
    return datetime.strptime(timestap, '%Y-%m-%d %H:%M:%S')


def get_csv_log(step=1, reduce_lines=None, samples_range=None):
    if os.path.isfile(csv_log_path):
        log = CSVParser(csv_log_path, step=step, reduce_lines=reduce_lines, samples_range=samples_range)
    else:
        csv_log_content = requests.get(f'{aquapi_address}/get_log').content
        log = CSVParser.from_bytes(csv_log_content, reduce_lines=reduce_lines, samples_range=samples_range)
    return log


def get_samples_range(samples_range):
    t0 = time.time()
    log = get_csv_log(samples_range=samples_range)
    log_data = log.get_columns_by_name("timestamp", "ph", "temperature", "relay")
    # log_data['timestamp'] = \
    #     list(
    #         map(lambda t: f"{datetime.strptime(t, '%Y-%m-%d %H:%M:%S'):%Y-%m-%dT%H:%M:%S}", log['timestamp'])
    # )
    #
    log_data['ph'] = \
        list(
            map(float, log['ph'])
        )

    log_data['temperature'] = \
        list(
            map(float, log['temperature'])
        )

    co2_relay_factor = (min(log_data["ph"]) - 0.05)
    log_data['relay'] = \
        list(
            map(lambda r: float(r) * co2_relay_factor, log['relay'])
        )

    resp = dict()
    for col in log.header:
        resp[col] = log_data[col]
    print(f"json send in {time.time() - t0}")
    return json.dumps(resp)


# ip_ban_list = ['82.197.187.146']
ip_ban_list = []


@app.before_request
def block_method():
    ip = request.environ.get('REMOTE_ADDR')
    if ip in ip_ban_list:
        abort(403)


@app.route("/")
def index():
    sidebar = render_template("templates/sidebar.html", dash_active='class="active"')
    log_data = get_samples_range(samples_range="-1")
    log_data = json.loads(log_data)

    gauge_js = render_template("js/gauge.js", init_ph=log_data["ph"], init_temp=log_data["temperature"])
    header_gauge_jsscript = render_template("templates/script.html", js_script=gauge_js)

    # charts
    with open('resources/js/plotly_templates.json') as t:
        templates = json.load(t)
    plotly_theme = json.dumps(templates['template_dark'])
    window_plotlyenv = render_template('js/window_plotyenv.js', template=plotly_theme, y_prim_range=[6.3, 7.8])
    update_plot_js_script = render_template("js/aquapi_chart_update.js", smooth_window=15)
    plotly_scripts = render_template('templates/plotly_script.html',
                                     plotly_plot=open('resources/js/plotly_plot.js').read(),
                                     ploty_env=window_plotlyenv,
                                     aquapi_update_js=open('resources/js/aquapi_chart_update.js').read(),
                                     update_plot_js_script=update_plot_js_script
                                     )

    common_jsscript = render_template("templates/script.html", js_script=render_template("js/common.js"))
    return render_template("templates/main.html", sidebar=sidebar,
                           header_jsscripts=[header_gauge_jsscript, common_jsscript, plotly_scripts])


@app.route("/gauge")
def gauge():
    gauge_js = render_template("js/gauge.js")
    header_jsscript = render_template("templates/script.html", js_script=gauge_js)
    return render_template("templates/gauge.html", header_jsscript=header_jsscript)


@app.route("/settings")
def settings():
    sidebar = render_template("templates/sidebar.html", settings_active='class="active"')
    return render_template("templates/main.html", content="EMPTY", sidebar=sidebar)


@app.route("/system")
def system():
    sidebar = render_template("templates/sidebar.html", system_active='class="active"')
    return render_template("templates/main.html", content="EMPTY", sidebar=sidebar)


@app.route("/log")
def log():
    lines_num = request.args.get('range', None)
    csv_log = get_csv_log(samples_range=lines_num)
    table = render_template("table/table.html", head_columns=csv_log.get_header(),
                            rows=csv_log.get_rows())
    sidebar = render_template("templates/sidebar.html", log_active='class="active"')
    return render_template("templates/main.html", content=table, sidebar=sidebar)


@app.route("/charts_old")
def charts_old():
    # TODO: add buttons and forms to configure how chart will be displayed and save it in json file
    ph_y_min, ph_y_max = 6.2, 7
    t0 = time.time()
    samples_range = request.args.get('range') or request.args.get('r')
    reduce_lines = not samples_range and 650
    log = get_csv_log(reduce_lines=reduce_lines, samples_range=samples_range)
    log_data = log.get_columns_by_name("timestamp", "ph", "temperature", "relay")

    dt_timestamps = list(map(timestamp_to_datetime, log_data['timestamp']))

    temperature_values = list(map(float, log_data['temperature']))
    tempr_df = DataFrame(data={'temperature': temperature_values, 'date': dt_timestamps})
    temp_trendline = px.scatter(tempr_df,
                                y='temperature',
                                x='date',
                                trendline="rolling",
                                trendline_options={'window': 10})
    temp_trendline.data[1].showlegend = True
    temp_trendline.data[1].marker['color'] = "#c93126"
    temp_trendline.data[1].name = "Temperature"

    ph_values = list(map(float, log_data['ph']))
    ph_df = DataFrame(data={'PH': ph_values, 'sample': range(len(ph_values)), 'date': dt_timestamps})

    ph_trendline = px.scatter(ph_df,
                              y='PH',
                              x='date',
                              trendline="rolling",
                              trendline_options={'window': 5})

    ph_trendline.data[1].showlegend = True
    ph_trendline.data[1].name = 'PH'

    relay_values = list(map(lambda v: int(v) * (ph_y_min + 0.1), log_data["relay"]))
    relay_status = DataFrame(data={'CO2ON': relay_values, 'date': dt_timestamps, 'color': '#c93126'})
    relay_status_plot = px.line(
        relay_status,
        y='CO2ON',
        x='date',
        template='plotly_dark'
    )
    relay_status_plot_data = relay_status_plot.data[0]
    relay_status_plot_data.showlegend = True
    relay_status_plot_data.name = "CO2_ON"
    relay_status_plot_data.line['color'] = "rgba(199, 152, 26, 0.5)"
    relay_status_plot_data.fill = 'tozeroy'
    relay_status_plot_data.fillcolor = "rgba(245, 187, 29, 0.5)"
    relay_status_plot_data.opacity = 0.5

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        ph_trendline.data[1],
        secondary_y=False
    )
    fig.add_trace(
        temp_trendline.data[1],
        secondary_y=True
    )

    fig.add_trace(relay_status_plot.data[0],
                  secondary_y=False,
                  )

    fig.layout.template = "plotly_dark"
    fig.update_layout(title_text="AQUAPI CHARTS")

    # Set y-axes titles
    fig.update_yaxes(title_text="<b>PH</b>", secondary_y=False, range=[ph_y_min, ph_y_max])
    fig.update_yaxes(title_text="<b>Temperature [C]</b>", secondary_y=True,
                     range=[20, 32])

    t_end = time.time() - t0

    fig.update_layout(legend=dict(
        yanchor="top",
        y=0.99,
        xanchor="left",
        x=0.01
    ))

    print(t_end, file=open('tstats.txt', 'a'))

    sidebar = render_template("templates/sidebar.html", charts_active='class="active"')
    fig_html = fig.to_html(full_html=False, default_height='80vh')
    return render_template("templates/main.html", content=fig_html, sidebar=sidebar)


@app.route("/charts")
def charts():
    with open('resources/js/plotly_templates.json') as t:
        templates = json.load(t)
    plotly_theme = json.dumps(templates['template_dark'])
    window_plotlyenv = render_template('js/window_plotyenv.js', template=plotly_theme, y_prim_range=[6.3, 7.8])

    content = render_template('templates/plotly_script.html',
                              plotly_plot=open('resources/js/plotly_plot.js').read(),
                              ploty_env=window_plotlyenv,
                              aquapi_update_js=open('resources/js/aquapi_chart_update.js').read()
                              )
    update_plot_js_script = render_template("js/aquapi_chart_update.js", smooth_window=15)
    header_jsscript = render_template("templates/script.html", js_script=update_plot_js_script)
    sidebar = render_template("templates/sidebar.html", charts_active='class="active"')
    return render_template("templates/main.html", content=content, sidebar=sidebar, header_jsscript=header_jsscript)


@app.route("/plot")
def plot():
    step = int(request.args.get('s', 1))
    log = get_csv_log(step=step)
    log_data = log.get_columns_by_name("timestamp", "ph", "temperature")
    ph_values = list(map(float, log_data['ph']))
    df = DataFrame(data={'PH': ph_values, 'PH2': ph_values,
                         'date': list(map(timestamp_to_datetime, log_data["timestamp"]))})
    fig = px.scatter(df,
                     x="date",
                     y="PH",
                     range_y=[min(ph_values) - 0.5, max(ph_values) + 0.5],
                     trendline="rolling",
                     trendline_options={'window': 5})
    fig.data = [t for t in fig.data if t.mode == "lines"]
    fig.update_traces(showlegend=True)
    fig.add_bar(name="CO2 relay", y=list(map(lambda v: int(v) * min(ph_values) - 0.1, log.relay)), x=df.date)
    return fig.to_html()


@app.route('/postaquapidata', methods=['POST'])
def foo():
    """
    reads data from post method
    :return:
    """
    global log_data
    data = request.json
    print(data)
    log_data = data
    return json.dumps({'status': 'OK'})


@app.route("/get_log", methods=['GET'])
def get_log():
    return open(csv_log_path).read()


@app.route("/get_json", methods=['GET'])
def get_json():
    return json.dumps(log_data)
    # samples_range = request.args.get('range') or request.args.get('r')
    # return get_samples_range(samples_range)


@app.route("/get_latest", methods=['GET'])
def get_latest():
    return get_samples_range(samples_range="-1")


@app.route("/get_dash_data", methods=['GET'])
def get_dash_data():
    latest_sample = json.loads(get_samples_range(samples_range="-1"))
    ph = latest_sample['ph'][0]
    kh = ph_controller.get_settings()['kh']
    co2 = 3 * kh * 10 ** (7 - ph)
    latest_sample["co2"] = co2
    return latest_sample


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
