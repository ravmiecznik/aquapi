#!/usr/bin/python3
import http
import json
import os
import time
import requests
from datetime import datetime
from collections import deque
from flask import Flask, request, render_template, abort
from subprocess import Popen, PIPE
from threading import Thread

import ph_controller
from ph_controller import CSVParser, log_file, logger, tstamp

this_path = os.path.dirname(__file__)


class ServerStatus:
    max_chart_len = 50
    log_data = {
        "timestamp": deque([], maxlen=max_chart_len),
        "ph": deque([], maxlen=max_chart_len),
        "temperature": deque([], maxlen=max_chart_len),
        "relay": deque([], maxlen=max_chart_len),
    }


try:
    aquapi_address = "http://188.122.24.160:5000"
    requests.get(f'{aquapi_address}', timeout=20)
except requests.exceptions.ConnectionError:
    aquapi_address = "http://192.168.55.250:5000"

app = Flask(__name__, template_folder="resources")
this_path = os.path.dirname(__file__)
csv_log_path = 'log.csv'


def read_init_data():
    data = CSVParser(log_file).get_data_as_dict()
    if not data["timestamp"]:
        data["timestamp"] = [tstamp()]
        for k in data:
            if k != "timestamp":
                data[k].append(0)
    else:
        data['relay'] = [(1 - d) * 6.5 for d in data['relay']]
    return data


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
    log_data = ServerStatus.log_data
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


@app.route('/postaquapidata', methods=['POST'])
def post_aquapi_data():
    """
    reads data from post method
    :return:
    """
    data = json.loads(request.json)
    for key in data:
        ServerStatus.log_data[key].extend(data[key])
    return json.dumps({'status': 'OK'})


@app.route("/get_aquapi_data", methods=['GET'])
def get_aquapi_data():
    """
    Gets aquapi data on
    :return:
    """
    t0 = time.time()
    data = {k: list(ServerStatus.log_data[k]) for k in ServerStatus.log_data}
    logger.info(f"get json in {time.time() - t0}")
    return json.dumps(data)


@app.route("/post_data_frame", methods=['POST'])
def post_data_frame():
    data = json.loads(request.json)
    for key in data:
        ServerStatus.log_data[key].append(data[key])
    return json.dumps({'status': 'OK'})


@app.route("/get_latest", methods=['GET'])
def get_latest():
    return get_samples_range(samples_range="-1")


@app.route("/get_dash_data", methods=['GET'])
def get_dash_data():
    log_data = ServerStatus.log_data
    latest_sample = {k: log_data[k][-1] for k in log_data}
    ph = latest_sample['ph']
    kh = ph_controller.get_settings()['kh']
    co2 = 3 * kh * 10 ** (7 - ph)
    latest_sample["co2"] = co2
    logger.info(latest_sample)
    logger.info(type(latest_sample))
    return json.dumps(latest_sample)


if __name__ == '__main__':
    init_data = read_init_data()
    log_data = {
        key: deque(init_data[key], maxlen=ServerStatus.max_chart_len) for key in init_data
    }
    ServerStatus.log_data = log_data
    app.run(debug=True, host='0.0.0.0')
