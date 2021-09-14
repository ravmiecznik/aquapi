#!/usr/bin/python3

import os
from flask import Flask, request, render_template, send_from_directory
from pandas import DataFrame, read_csv
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pprint import pformat, pprint

app = Flask(__name__, template_folder="resources")
this_path = os.path.dirname(__file__)


class CSVParser:
    def __init__(self, csv_path, sep=';'):
        self.__csv_path = csv_path
        self.__sep = sep
        self.header = self.get_header()

    def get_header(self):
        with open(self.__csv_path) as f:
            header = f.readline().strip()
        return header.split(self.__sep)

    def get_rows(self):
        rows = list()
        with open(self.__csv_path) as f:
            f.readline()
            for line in f:
                rows.append(line.split(self.__sep))
        return rows

    def get_column(self, index):
        column = list()
        with open(self.__csv_path) as f:
            f.readline()
            for line in f:
                column.append(line.strip().split(self.__sep)[index])
        return column

    def get_columns(self, *indexes):
        columns = [list() for _ in indexes]
        with open(self.__csv_path) as f:
            f.readline()
            for line in f:
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

@app.route("/")
def index():
    f = open('/home/aquapi/ph_guard/log.csv')
    col_size = 20
    header = '|'.join("{:>{siz}}".format(col, siz=col_size) for col in f.readline().split(';')).replace(' ', '_')
    lines_num = int(request.args.get('l', 50))
    lines = [header]
    new_lines = f.readlines()[-lines_num:]
    new_lines = list(
        map(lambda line: '|'.join("{:>{siz}}".format(col, siz=col_size) for col in line.split(';')).replace(' ', '_'),
            new_lines))
    lines.extend(new_lines)
    f.close()
    return '<br>'.join(lines)

@app.route("/table")
def table():
    csv_log = CSVParser('/home/aquapi/ph_guard/log.csv')
    return render_template("table/table.html", head_columns=csv_log.get_header(),
    rows=csv_log.get_rows())


@app.route("/plot2")
def plot2():
    log = CSVParser('/home/aquapi/ph_guard/log.csv')
    log_data = log.get_columns_by_name("ph", "temperature", "relay")


    tempr_values = list(map(float, log_data['temperature']))
    tempr_df = DataFrame(data={'temperature': tempr_values, 'sample': range(len(tempr_values))})

    ph_values = list(map(float, log_data['ph']))
    ph_df = DataFrame(data={'PH': ph_values, 'sample': range(len(ph_values))})

    ph_trendline = px.scatter( ph_df,
                            trendline="rolling",
                            trendline_options={'window':5} )

    relay_values = list(map(lambda v:min(ph_values)*int(v)+0.03, log_data["relay"]))

    temp_trendline = px.scatter( tempr_df,
                            trendline="rolling",
                            trendline_options={'window':10} )
    temp_trendline.data[1].showlegend = True
    temp_trendline.data[1].marker['color'] = "#c93126"
    pprint(dir(temp_trendline))
    ph_trendline.data[1].showlegend = True

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        ph_trendline.data[1],
        secondary_y=False
        )
    fig.add_trace(
        temp_trendline.data[1],
        secondary_y=True
        )

    fig.update_layout(title_text="AQUAPI<br>PH, Temperature and CO2 relay status")

    # Set y-axes titles
    fig.update_yaxes(title_text="<b>PH</b>", secondary_y=False, range=[min(ph_values), max(ph_values)+0.2])
    fig.update_yaxes(title_text="<b>Temperature [C]</b>", secondary_y=True, range=[min(tempr_values)-2, max(tempr_values)+1])
    fig.add_bar(name="CO2 relay", y=relay_values)
    return fig.to_html()

@app.route("/plot")
def plot():
    log = CSVParser('/home/aquapi/ph_guard/log.csv')
    log_data = log.get_columns_by_name("ph", "temperature")
    ph_values = list(map(float, log_data['ph']))
    # for v in log.ph:
    #     try:
    #         ph_values.append(float(v))
    #     except ValueError:
    #         pass
    ph_values_len = len(ph_values)
    df = DataFrame(data={'PH': ph_values, 'PH2': ph_values, 'sample': range(ph_values_len)})
    fig = px.scatter(df,
                     x="sample",
                     y="PH",
                     range_y=[min(ph_values)-0.5, max(ph_values)+0.5],
                     trendline="rolling",
                     trendline_options={'window':5})
    #fig = px.bar(ph_values, range_y=[5, 9])
    #        dict(window=5, win_type="gaussian", function_args=dict(std=2)))
    fig.data = [t for t in fig.data if t.mode == "lines"]
    fig.update_traces(showlegend=True)
    fig.add_bar(name="CO2 relay", y=list(map(lambda v: int(v)*min(ph_values)-0.1, log.relay)))
    return fig.to_html()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
