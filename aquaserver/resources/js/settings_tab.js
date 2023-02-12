function update_calibration_stats(data) {
    ph_value = document.getElementById("ph-reading")
    ph_value_raw = document.getElementById("ph-reading-raw")
    ph_value.textContent = data["ph"]
    ph_value_raw.textContent = data["ph_raw"]
  }
  
  
  function get_calibration_data() {
    send_get_request("/get_calibration_data", update_calibration_stats);
  }

function start_calibration_data_reading(){
  var start_calibration_data_reading_job = setInterval(get_calibration_data, 2000);
  set_interval_jobs.push(start_calibration_data_reading_job);
}