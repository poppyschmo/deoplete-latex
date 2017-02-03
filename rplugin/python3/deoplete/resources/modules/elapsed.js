'use strict';

if (typeof process.hrtime === 'undefined')
  module.exports = make_stopwatch_d();
else
  module.exports = make_stopwatch_p();


function make_stopwatch_p() {
  var baseline = process.hrtime();
  return function _get_elapsed(reset) {
    if (reset)
      baseline = process.hrtime();
    var [a, b] = process.hrtime(baseline);
    return ( a * 1E9 + b ) / 1E6;
  };
}

function make_stopwatch_d() {
  var baseline = Date.now();
  return function _get_elapsed(reset) {
    // A negative reset val returns last reading before reset;
    var cached = Date.now() - baseline;
    if (reset)
      baseline = Date.now();
    return (reset > 0) ?  Date.now() - baseline : cached;
  };
}


