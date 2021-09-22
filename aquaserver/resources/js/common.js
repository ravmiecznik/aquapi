/**
 * GLOBAL STORAGES
 */
var xmlhttp_requests = Array();   //stores xmlhttp requests
var set_interval_jobs = Array();  //stores setInterval routines

/**
 * Calculates linear interpolated value between two points (values)
 * @param {input value} inval 
 * @param {min val} in_min 
 * @param {max val} in_max 
 * @param {map to out min} out_min 
 * @param {map to out max} out_max 
 * @returns 
 */
function map_val(inval, in_min, in_max, out_min, out_max){
  return (inval - in_min) * (out_max - out_min) / (in_max - in_min) + out_min;
}


/**
 * Sends get request
 */
 function send_get_request(request, on_ready_function) {
  console.log(request)
  var xmlhttp = new XMLHttpRequest();
  xmlhttp.onreadystatechange = function() {
    if (this.readyState == 4 && this.status == 200) {
      var data = JSON.parse(this.responseText);
      on_ready_function(data);
      xmlhttp_requests.shift();
    }
  };
  xmlhttp.onerror = function() {
    xmlhttp_requests.shift();
  }
  xmlhttp.open("GET", window.location.origin + request, true);
  if(xmlhttp_requests.length < 3){
    xmlhttp.send();
    xmlhttp_requests.push(xmlhttp);
  }
  else{
      console.log("Wait because of count: " + xmlhttp_requests.length);
  }
}

/**
 * Cleans content_div 
 */
function clean_content_div() {
  xmlhttp_requests.forEach((item, i) => {
    while (xmlhttp_requests.length > 0) {
      xmlhttp_requests.pop().abort();
    }
  });

  while(set_interval_jobs.length > 0){
    clearInterval(set_interval_jobs.pop());
  }
  content_div.innerHTML = "";
}

/**
 * Creates new gauge cell
 * @param {document.id} id 
 * @returns div with gauge
 */
function create_gauge_cell(id) {
  var gauge_cell = document.createElement("div");
  gauge_cell.className = "gauge_cell";
  var gauge_type = document.createElement("div");
  gauge_type.id = id;
  gauge_cell.appendChild(gauge_type);
  return gauge_cell;
}

/**
 * Sets only one button active
 * @param {button} button     a button to be activated
 * @param {Array} all_buttons all buttons will be deactivated
 */
function one_button_active(button, all_buttons) {
  all_buttons.forEach((item, i) => {
    item.className = "inactive";
  });
  button.className = "active";
}

/**
 * Renders dash view
 * @param {button} button 
 * @param {Array} buttons 
 */
function render_dash(button, buttons) {
  one_button_active(button, buttons);
  if (document.getElementById("gauge_grid") == null) {
    let content_div = document.getElementById("content_div");
    var gauge_grid = document.createElement("div");
    clean_content_div();
    gauge_grid.className = "gauge_grid";
    gauge_grid.id = "gauge_grid";
    button.className = "active";
    gauge_grid.appendChild(create_gauge_cell("gauge_ph"));
    gauge_grid.appendChild(create_gauge_cell("gauge_temperature"));
    gauge_grid.appendChild(create_gauge_cell("gauge_co2"));
    content_div.appendChild(gauge_grid);
    init_gauges();
  }
}

/**
 * Renders charts view
 * @param {button} button 
 * @param {Array} buttons 
 */
function render_charts(button, buttons) {
  one_button_active(button, buttons);
  if (document.getElementById("aquapi") == null) {
    let content_div = document.getElementById("content_div");
    let aquapi_plot_div = document.createElement("div");
    clean_content_div();
    aquapi_plot_div.id = "aquapi-plot";
    content_div.appendChild(aquapi_plot_div);
    init_charts();
    init_charts_update_job();
  }
}

/**
 * Init function
 */
function init() {
  let content_div = document.getElementById("content_div");
  content_div.request_jobs = Array();

  dash_button = document.getElementById("dash_button");
  charts_button = document.getElementById("charts_button");

  var buttons = [dash_button, charts_button];

  dash_button.className = "inactive";
  dash_button.onclick = function () { render_dash(dash_button, buttons) };

  charts_button.className = "inactive";
  charts_button.onclick = function () { render_charts(charts_button, buttons) };

  render_dash(dash_button, buttons);
}

window.onload = init;
