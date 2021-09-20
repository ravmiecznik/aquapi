//https://plotly.com/javascript/plotlyjs-function-reference

function smooth_array(array, window={{smooth_window if smooth_window else 20}}) {
  var new_array = Array();
  shift = Math.floor(window/2);
  new_array = array.slice(0, shift);   //start new array with initial values
  for (let i = 0; i < array.length; i++) {
    slice = array.slice(i, i + window)
    let avg = slice.reduce((a, v, i) => (a * i + v) / (i + 1));
    new_array[i+shift] = avg;
  }
  return new_array;
}

function update_auqapi_plot(data) {
  plot_div = document.getElementById("aquapi-plot")
  time_stamps = data["timestamp"]
  values_ph = data["ph"]
  values_temperature = data["temperature"]
  values_relay = data["relay"]

  // var na = data["ph"].slice();
  // var data = {
  //   y: na,
  //   type: 'scatter',
  //   mode: 'lines',
  //   marker: {color: 'green'}
  // }

  // Plotly.addTraces(plot_div, data)

  values_ph = smooth_array(values_ph);
  values_temperature = smooth_array(values_temperature);

  Plotly.update(plot_div, {
    'x': Array(time_stamps)
  });
  Plotly.update(plot_div, {
    'y': Array(values_ph)
  }, {}, [0]);
  Plotly.update(plot_div, {
    'y': Array(values_temperature)
  }, {}, [1]);
  Plotly.update(plot_div, {
    'y': Array(values_relay)
  }, {}, [2]);



  return plot_div
}


function get_json_log_data() {
  // plot_div = document.getElementById("aquapi-plot")
  // Plotly.relayout(plot_div, {
  //   'template': template_dark})
  var xmlhttp = new XMLHttpRequest();
  var url = "myTutorials.txt";

  xmlhttp.onreadystatechange = function() {
    if (this.readyState == 4 && this.status == 200) {
      var myArr = JSON.parse(this.responseText);
      update_auqapi_plot(myArr);
    }
  };

  xmlhttp.open("GET", window.location.origin + "/get_json", true);
  xmlhttp.send();

}

window.onload = get_json_log_data;
