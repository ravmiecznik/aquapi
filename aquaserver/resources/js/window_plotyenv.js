

window.PLOTLYENV = window.PLOTLYENV || {};
if (document.getElementById("aquapi-plot")) {
  Plotly.newPlot("aquapi-plot", [{
    "hovertemplate": "<b>Rolling mean trendline</b><br><br>date=%{x}<br>PH=%{y} <b>(trend)</b><extra></extra>",
    "legendgroup": "",
    "marker": {
      "color": "#636efa",
      "symbol": "circle"
    },
    "mode": "lines",
    "name": "PH",
    "showlegend": true,
    "type": "scatter",
    "x": [],
    "xaxis": "x",
    "y": [],
    "yaxis": "y"
  }, {
    "hovertemplate": "<b>Rolling mean trendline</b><br><br>date=%{x}<br>temperature=%{y} <b>(trend)</b><extra></extra>",
    "legendgroup": "",
    "marker": {
      "color": "#c93126",
      "symbol": "circle"
    },
    "mode": "lines",
    "name": "Temperature",
    "showlegend": true,
    "type": "scatter",
    "x": [],
    "xaxis": "x",
    "y": [],
    "yaxis": "y2"
  }, {
    "fill": "tozeroy",
    "fillcolor": "rgba(245, 187, 29, 0.5)",
    "hovertemplate": "date=%{x}<br>CO2ON=%{y}<extra></extra>",
    "legendgroup": "",
    "line": {
      "color": "rgba(199, 152, 26, 0.5)",
      "dash": "solid"
    },
    "marker": {
      "symbol": "circle"
    },
    "mode": "lines",
    "name": "CO2_ON",
    "opacity": 0.5,
    "orientation": "v",
    "showlegend": true,
    "type": "scatter",
    "x": [],
    "xaxis": "x",
    "y": [],
    "yaxis": "y"
  }], {
    "legend": {
      "x": 0.01,
      "xanchor": "left",
      "y": 0.99,
      "yanchor": "top"
    },
    "template": {{template|safe if template else "template_plotly"}},
    "title": {
      "text": "AQUAPI CHARTS"
    },
    "xaxis": {
      "anchor": "y",
      "domain": [0.0, 0.94]
    },
    "yaxis": {
      "anchor": "x",
      "domain": [0.0, 1.0],
      "range": [6.2, 7],
      "title": {
        "text": "<b>PH</b>"
      }
    },
    "yaxis2": {
      "anchor": "x",
      "overlaying": "y",
      "range": [20, 32],
      "side": "right",
      "title": {
        "text": "<b>Temperature [C]</b>"
      }
    }
  }, {
    "responsive": true
  })
};
