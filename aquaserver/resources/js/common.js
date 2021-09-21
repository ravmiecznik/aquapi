function clean_content(){
  function cleari(i){
    clearInterval(i);
  }
  let content_div = document.getElementById("content_div");
  console.log("ids " + content_div.intervalIds);
  content_div.intervalIds.forEach(clearInterval);
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
  clean_content();
  let content_div = document.getElementById("content_div");
  let aquapi_plot_div = document.createElement("div");
  aquapi_plot_div.id = "aquapi-plot";
  content_div.appendChild(aquapi_plot_div);
  init_charts();
  init_charts_update();
}

function init(){
  let content_div = document.getElementById("content_div");
  content_div.intervalIds = Array();

  dash_button = document.getElementById("dash_button");
  dash_button.onclick = render_dash;

  charts_button = document.getElementById("charts_button");
  charts_button.onclick = render_charts;

  render_dash();
}

window.onload = init;
