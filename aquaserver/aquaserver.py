#!/usr/bin/python3

import os
import time
from datetime import datetime
from io import BufferedRandom
from pprint import pprint
import tempfile

import plotly.express as px
import requests
from flask import Flask, request, render_template
from pandas import DataFrame
from plotly.subplots import make_subplots

app = Flask(__name__, template_folder="resources")
this_path = os.path.dirname(__file__)
csv_log_path = 'log.csv'
aquapi_address = "http://192.168.55.250:5000"


class CSVParser:
    def __init__(self, csv_path, sep=';', step=1, reduce_lines=None, samples_range=None):
        if type(csv_path) == tempfile._TemporaryFileWrapper:
            self.__temp_file = csv_path     # keep it alive
            csv_path = self.__temp_file.name
            print(csv_path)
        self.__csv_path = csv_path
        self.__sep = sep
        self.header = self.get_header()
        if reduce_lines:
            self.__step = self.lines_count() // reduce_lines
        else:
            self.__step = step
        self.__slice = slice(0, None)
        if samples_range:
            if ':' in samples_range:
                start, stop = list(map(int, samples_range.split(':')))
            else:
                start = int(samples_range)
                stop = None
            self.__slice = slice(start, stop)

    @classmethod
    def from_bytes(cls, content, **kwargs):
        temp_file = tempfile.NamedTemporaryFile(mode='w+b')
        temp_file.write(content)
        return cls(temp_file, **kwargs)

    def lines_count(self):
        count = 0
        with open(self.__csv_path) as f:
            f.readline()
            for _ in f:
                count += 1
        return count

    def get_header(self):
        with open(self.__csv_path) as f:
            header = f.readline().strip()
        return header.split(self.__sep)

    def get_rows(self):
        rows = list()
        with open(self.__csv_path) as f:
            f.readline()
            for i, line in enumerate(f):
                if not (i % self.__step):
                    rows.append(line.split(self.__sep))
        return rows[self.__slice]

    def get_column(self, index):
        column = list()
        with open(self.__csv_path) as f:
            f.readline()
            for i, line in enumerate(f):
                if not (i % self.__step):
                    column.append(line.strip().split(self.__sep)[index])
        return column[self.__slice]

    def get_columns(self, *indexes):
        columns = [list() for _ in indexes]
        with open(self.__csv_path) as f:
            f.readline()
            lines = f.readlines()[self.__slice]
            for i, line in enumerate(lines):
                if not (i % self.__step):
                    cols = line.strip().split(self.__sep)
                    [columns[i].append(cols[j]) for i, j in enumerate(indexes)]
        return columns

    def get_columns_by_name(self, *columns):
        indexes = [self.header.index(column_name) for column_name in columns]
        columns_by_indexes = self.get_columns(*indexes)
        columns_by_name = dict()
        for i, column in enumerate(columns):
            columns_by_name[column] = columns_by_indexes[i]
        return columns_by_name

    def __getattr__(self, item):
        col_index = self.header.index(item)
        return self.get_column(col_index)


def timestamp_to_datetime(timestap):
    return datetime.strptime(timestap, '%Y-%m-%d %H:%M:%S')


def get_csv_log(step=1, reduce_lines=None, samples_range=None):
    if os.path.isfile(csv_log_path):
        log = CSVParser(csv_log_path, step=step, reduce_lines=reduce_lines, samples_range=samples_range)
    else:
        csv_log_content = requests.get(f'{aquapi_address}/get_log').content
        log = CSVParser.from_bytes(csv_log_content, reduce_lines=reduce_lines, samples_range=samples_range)
    return log


@app.route("/")
def index():
    sidebar = render_template("pages/sidebar.html", dash_active='class="active"')
    return render_template("pages/main.html", content=f'<img src="/static/swordfish.png" alt="User Image">', sidebar=sidebar)


@app.route("/settings")
def settings():
    sidebar = render_template("pages/sidebar.html", settings_active='class="active"')
    return render_template("pages/main.html", content="EMPTY", sidebar=sidebar)


@app.route("/system")
def system():
    sidebar = render_template("pages/sidebar.html", system_active='class="active"')
    return render_template("pages/main.html", content="EMPTY", sidebar=sidebar)


@app.route("/log")
def log():
    lines_num = request.args.get('range', None)
    csv_log = get_csv_log(samples_range=lines_num)
    table = render_template("table/table.html", head_columns=csv_log.get_header(),
                           rows=csv_log.get_rows())
    sidebar = render_template("pages/sidebar.html", log_active='class="active"')
    return render_template("pages/main.html", content=table, sidebar=sidebar)


@app.route("/charts")
def charts():
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

    relay_values = list(map(lambda v: int(v)*(ph_y_min + 0.1), log_data["relay"]))
    relay_status = DataFrame(data={'CO2ON': relay_values, 'date': dt_timestamps, 'color': '#c93126'})
    relay_status_plot = px.line(
        relay_status,
        y='CO2ON',
        x='date',
    )
    relay_status_plot_data = relay_status_plot.data[0]
    relay_status_plot_data.showlegend = True
    relay_status_plot_data.name = "CO2_ON"
    relay_status_plot_data.line['color'] = "rgba(199, 152, 26, 0.5)"
    relay_status_plot_data.fill = 'tozerox'
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
    # fig.add_bar(name="CO2 relay", y=relay_values, x=dt_timestamps)

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

    sidebar = render_template("pages/sidebar.html", charts_active='class="active"')
    fig_html = fig.to_html(full_html=False, default_height='80vh')
    return render_template("pages/main.html", content=fig_html, sidebar=sidebar)


@app.route("/test")
def test():
    return render_template('test.html', plotly_plot=open('resources/js/plotly_plot.js').read(),
                           ploty_env=open('resources/js/window_plotyenv.js').read())


@app.route("/plot")
def plot():
    step = int(request.args.get('s', 1))
    log = get_csv_log(step=step)
    log_data = log.get_columns_by_name("timestamp", "ph", "temperature")
    ph_values = list(map(float, log_data['ph']))
    df = DataFrame(data={'PH': ph_values, 'PH2': ph_values,
                         'date': list(map(timestamp_to_datetime, log_data["timestamp"]))})
    pprint(list(map(lambda tstamp: tstamp.split()[0], log_data["timestamp"])))
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


@app.route('/foo', methods=['POST'])
def foo():
    """
    reads data from post method
    :return:
    """
    data = request.json
    # return jsonify(data)


@app.route("/get_log", methods=['GET'])
def get_log():
    return open(csv_log_path).read()


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
