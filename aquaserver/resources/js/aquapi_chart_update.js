//https://plotly.com/javascript/plotlyjs-function-reference

var last_chart_data = null;

function smooth_array(array, window={{smooth_window if smooth_window else 20}}) {  //jinja expression not an error
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

function update_aquapi_plot(data) {
  plot_div = document.getElementById("aquapi-plot")
  time_stamps = data["timestamp"]
  values_ph = data["ph"]
  values_temperature = data["temperature"]
  values_relay = data["relay"]

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
  last_chart_data = data;
  document.getElementById("timestamp").textContent = data["timestamp"][data["timestamp"].length -1]
  return plot_div
}

function get_json_log_data(range="") {
  send_get_request("/get_json" + range, update_aquapi_plot);
}

function init_charts_update_job(){
  if(last_chart_data != null){
    update_aquapi_plot(last_chart_data);
  }
  get_json_log_data();
  var update_charts_job = setInterval(get_json_log_data, 10000, "?range=-2000");
  set_interval_jobs.push(update_charts_job);
}
