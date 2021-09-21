var xmlhttp_requests = Array();

function clean_content(){
  xmlhttp_requests.forEach((item, i) => {
    while(xmlhttp_requests.length > 0){
      xmlhttp_requests.pop().abort();
    }
  });

  function cleari(i){
    clearInterval(i);
  }
  let content_div = document.getElementById("content_div");
  console.log("ids " + content_div.request_jobs);
  while(content_div.request_jobs.length > 0){
    content_div.request_jobs.forEach((item, i) => {
      clearInterval(content_div.request_jobs.pop());
    });
  }
  ;
  content_div.innerHTML = "";
}

function create_gauge_cell(id){
  var gauge_cell = document.createElement("div");
  gauge_cell.className = "gauge_cell";
  var gauge_type = document.createElement("div");
  gauge_type.id = id;
  gauge_cell.appendChild(gauge_type);
  return gauge_cell;
}

function render_dash() {

  let content_div = document.getElementById("content_div");
  var gauge_grid = document.createElement("div");
  if(document.getElementById("gauge_grid") == null){
    clean_content();
    gauge_grid.className = "gauge_grid";
    gauge_grid.id = "gauge_grid";
    gauge_grid.appendChild(create_gauge_cell("gauge_ph"));
    gauge_grid.appendChild(create_gauge_cell("gauge_temperature"));
    gauge_grid.appendChild(create_gauge_cell("gauge_co2"));
    content_div.appendChild(gauge_grid);
    init_gauges();
  }
}

function render_charts() {

  if(document.getElementById("aquapi") == null){
    let content_div = document.getElementById("content_div");
    let aquapi_plot_div = document.createElement("div");
    clean_content();
    aquapi_plot_div.id = "aquapi-plot";
    content_div.appendChild(aquapi_plot_div);
    init_charts();
    init_charts_update();
  }
}

function transferComplete(evt) {
  console.log("The transfer is complete." + evt);
}

function init(){
  let content_div = document.getElementById("content_div");
  content_div.request_jobs = Array();

  dash_button = document.getElementById("dash_button");
  dash_button.onclick = render_dash;

  charts_button = document.getElementById("charts_button");
  charts_button.onclick = render_charts;

  render_dash();
}

window.onload = init;
