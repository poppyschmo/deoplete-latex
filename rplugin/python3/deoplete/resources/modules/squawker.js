'use strict';

const elapsed = require('./elapsed.js');

module.exports = make_squawker;

// Levels are same as those found in Linux syslog(3).
const log_levels = [ 'emerg', 'alert', 'crit', 'err',
                      'warn', 'notice', 'info', 'debug', ];

// Unsure of how best to handle console window support. For now, just hard-code
// to 80.
var width = (typeof process.stdout === 'undefined') ? 80 : 0;

function get_padlen(textwidth, lhlen, rhlen) {
  let lhsafe = lhlen % textwidth;
  if (lhsafe > textwidth - rhlen)
    return 2 * textwidth - lhsafe - rhlen;
  else {
    return textwidth - lhsafe - rhlen;
  }
}

function make_squawker(max, verbose) {
  // Return a dumb logger that simply appends time elapsed to every call.
  let thresh = log_levels.indexOf(max);
  if (!width)
    width = process.stdout.getWindowSize()[0];
  elapsed(true) && squawker('Squawky: stopwatch initialized...', 7);
  //
  function squawker(msg='default', priority='debug') {
    // Unlike syslog, here, the message comes first.
    let level = typeof priority === 'string' ? log_levels.indexOf(priority)
                                              : Number(priority);
    // XXX - When wrapping lines, gets a bit crowded. Perhaps add indent on lhs
    // or wrap at `textwidth - len(ts)`. Or add a bit more padding on rhs margin.
    let composed_msg = `${log_levels[level]}: ${msg}`;
    //
    let el = elapsed();
    // Padding of 1 digit to compensate for loss of least significant zeroes.
    let ts, padding;
    if (el <= 9000) {
      let under = String(el).length - String(el).indexOf('.') - 1;
      let msp = under < 6 ? '0'.repeat(6 - under) : '';
      ts = `${el}${msp} ms`;
      let pl = get_padlen(width, composed_msg.length, String(ts).length);
      padding = ' '.repeat(pl);
    } else {
      let parts = String(el/1000).split('.');
      let ssp = (parts[1] + '000000').substr(0, 6);
      ts = parts[0] + '.' + ssp + ' s';
      let pl = get_padlen(width, composed_msg.length, String(ts).length) - 1;
      padding = ' '.repeat(pl);
    }
    //
    (verbose && level <= thresh ) &&
      console.log(composed_msg + padding + ts);
  }
  return squawker;
}

