#!/usr/bin/python3

from flask import Flask, request
import plotly.express as px

app = Flask(__name__)


class CSVParser:
    def __init__(self, csv_path, sep=';'):
        self.__csv_path = csv_path
        self.__sep = sep
        self.header = self.get_header()

    def get_header(self):
        with open(self.__csv_path) as f:
            header = f.readline().strip()
        return header.split(self.__sep)

    def get_column(self, index):
        column = list()
        with open(self.__csv_path) as f:
            f.readline()
            for line in f:
                column.append(line.strip().split(self.__sep)[index])
        return column

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

@app.route("/plot")
def plot():
    log = CSVParser('/home/aquapi/ph_guard/log.csv')
    ph_values = list()
    for v in log.ph:
        try:
            ph_values.append(float(v))
        except ValueError:
            pass
    ph_values_len = len(ph_values)
    fig = px.scatter(x=range(ph_values_len),
                     y=ph_values, range_y=[min(ph_values)-0.5, max(ph_values)+0.5],
                     trendline="rolling",
                     trendline_options={'window':5})
    #fig = px.bar(ph_values, range_y=[5, 9])
    #        dict(window=5, win_type="gaussian", function_args=dict(std=2)))
    fig.data = [t for t in fig.data if t.mode == "lines"]
    fig.update_traces(showlegend=True)
    fig.add_bar(y=list(map(lambda v: int(v)*min(ph_values)-0.1, log.relay)))
    return fig.to_html()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
