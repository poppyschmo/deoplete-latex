
'use strict';

const mjAPI = require('mathjax-node/lib/mj-single.js');
const fs = require('fs');
const squawker = require('./modules/squawker.js');
const master_list = require('./lists/update_asm_mj.json');
const outfile = 'lists/update_mathjax.json';

var VERBOSE = true;
var LOGMAX = 'info';
var squawk = squawker(LOGMAX, VERBOSE);
var append_guesses = ['{}', '{}{}', '{x}', '{a}{b}', '(', ')'];

mjAPI.start();

function get_stats(fpath) {
  return new Promise(function _gstats_prom_cb(resolve, reject) {
    fs.stat(fpath, (err, stats) => {
      if (err) reject(err);
      resolve(stats);
    });
  });
}

function* move_existing(fpath) {
  let statobj;
  try {
    statobj = yield get_stats(fpath);
  } catch(err) {
    if (err.message.search(/ENOENT: no such file or directory/) >= 0) {
      squawk(`No existing file named "${fpath}". Writing anyway...`, 6);
      return 1;
    } else {
      squawk(`Error finding file "${fpath}", ${err.message}, Quitting`, 3);
      return 0;
    }
  }
  let stamp = statobj.mtime.toISOString();
  let parts = stamp.match(/([\d-]+)T([\d:]+)\./);
  let suffix = '.' + parts[1].replace(/[-]/g, '') + '_' +
                parts[2].replace(/[:]/g, '') + '.bak';
  let oldpath = fpath;
  let newpath = fpath.replace('.json', '') + suffix;
  return yield new Promise(function _rename_prom_cb(resolve, reject) {
    fs.rename(fpath, newpath, (err) => {
      if (err) reject(err);
      squawk(`Moved "${oldpath}" to "${newpath}"`, 6);
      resolve(1);
    });
  });
}

function save_updated_list(out_name) {
  return new Promise(function _writeFile_prom_cb(resolve, reject) {
    fs.writeFile(out_name, JSON.stringify(master_list, null, 2), (err) => {
      if (err) reject(err);
      resolve(`Wrote "${out_name}"`);
    });
  });
}

function askMJ(tex_cmd) {
  //
  // Helper funcs
  function exclude_abcs(char) {
    let x = char.codePointAt();
    let [a, z, A, Z] = ['a', 'z', 'A', 'Z'].map((c) => c.codePointAt());
    return ( (x < A || x > z) || (x > Z && x < a) ) ?
            `U+${x.toString(16).toUpperCase()}` : undefined;
  }
  function get_codepoints(s) {
    // returns array of human-readable codepoints
    let outarr = s.split('').map(exclude_abcs);
    return outarr.every((x) => (x)) ? outarr : undefined;
  }
  //
  return new Promise(function _askMJ_prom_cb(resolve, reject) {
    mjAPI.typeset(
      {
        math: tex_cmd,
        format: 'TeX',
        html:true,
        speakText: true,
      },
      function (data) {
        if (data.errors) {
          reject(data.errors);
        }
        else {
          let human = data.speakText;
          let sym = data.html.split(/<[^>]+>/).join('');
          let codept = get_codepoints(sym);
          resolve({'symbol': sym, 'codepoints': codept, 'speaktext': human});
        }
      }
    );
  });
}

function* iter_list() {
  for (let key in master_list) {
    let item = master_list[key];
    if ( item.name.startsWith('\\') && item.mode.indexOf('math') >= 0 )
      yield item.name;
    /*
     * if ( item.name.startsWith('\\') && item.symbol === null
     *                                 && item.mode.indexOf('math') >= 0 ) {
     *   yield item.name;
     * }
     */
  }
}

function* try_iter(tex_cmd) {
  /* Void. Arbitrary separation of `main`'s logic */
  let test_args = Array.from(append_guesses, (x) => tex_cmd + x );
  for (let trial of test_args) {
    try {
      let candidate = yield askMJ(trial);
      if ( append_guesses.indexOf(candidate.symbol) >= 0  ||
            candidate.symbol === '' )
        continue;
      else {
        let sym_pat =/^\(\)$|^[abx]?[{(]?[?abx]+[})]?[abx]?$/;
        if ( candidate.symbol.search( sym_pat ) >= 0 ) {
          squawk(`try_iter rejected sym: ${candidate.symbol}`, 6);
          // console.log(`try_iter rejected sym: ${candidate.symbol}`);
          candidate.symbol = undefined;
          candidate.codepoints = undefined;
        }
        if (['x', 'x x', 'a b', 'b a', 'b'].indexOf(candidate.speaktext) >= 0
              || ['question-mark question-mark'].reduce(
                  (p, q) => p + candidate.speaktext.indexOf(q), 0) >= 0) {
          squawk(`try_iter rejected speaktext: ${candidate.speaktext}`, 6);
          // console.log(`try_iter rejected speaktext: ${candidate.speaktext}`);
          candidate.speaktext = undefined;
        }
        if (!candidate.speaktext && !candidate.symbol && !candidate.codepoints)
          continue;
        return candidate;
      }
    } catch (err) {
      if (err.join('').search(/parse|argument/i))
        continue;
      else {
        squawk(`mjAPI rejected ${trial} with error: ${err}`, 6);
        // console.error(`mjAPI rejected ${trial} with error:`, err);
        break;
      }
    }
  }
}

function* main() {
  let it = iter_list();
  let review_d = {}; // Collect results in this dict...
  let errors = [];
  for ( let tex_next, max_run = 0, break_after = Number.MAX_SAFE_INTEGER;
        //
        (tex_next = yield it.next())
          && !tex_next.done
          && max_run < break_after;
        //
        max_run++ ) {
    //
    let result = yield* try_iter(tex_next.value);
    //
    if (result)
      review_d[tex_next.value] = result;
  }
  //
  for (let key in review_d) {
    // Append codepoint and speaktext to meta entries
    let cp = review_d[key].codepoints ?
              review_d[key].codepoints.join(', ') : '';
    let speaktext = review_d[key].speaktext ? review_d[key].speaktext : '';
    //
    let ex_meta = master_list[key].meta ? master_list[key].meta : {};
    if (cp && !ex_meta.codepoints)
      ex_meta.codepoints = cp;
    if (speaktext && !ex_meta.speaktext)
      ex_meta.speaktext = speaktext;
    review_d[key].meta = ex_meta;
    // Update master_list's `.meta` entries...
    master_list[key].meta = ex_meta;
    //
    let ex_symbol = master_list[key].symbol;
    // Complain if existing symbol conflicts with MathJax version...
    if ( ex_symbol && ex_symbol !== review_d[key].symbol) {
      errors.push( new Error(`symbol mismatch: ${key}, master: ${ex_symbol}, ` +
                              `mj: ${review_d[key].symbol}`) );
    }
    else if (!ex_symbol && review_d[key].symbol) // Update master_list...
      master_list[key].symbol = review_d[key].symbol;

  }
  // console.log(review_d);
  if (yield* move_existing(outfile)) {
    squawk(yield save_updated_list(outfile), 5);
  }
  //
  errors.forEach(function _complain(err) {
    console.error(err);
  });
}

function run(gen, ...args) {
  // From YDKJS: https://github.com/getify/You-Dont-Know-JS
  //
  // Initialize the generator in the current context...
  var it = gen.apply( this, args );
  //
  // Return a Promise for the generator completing. Helpful for handling
  // exceptions thrown by run(...) itself via native Promise syntax like
  // `.catch()`, as opposed to wrapping in try/catch. Promise is fully
  // resolved with undefined resolution val or `false` on error.
  return Promise.resolve()
    .then( function handleNext(value) { // Main fulfillment handler. `value` is
                                        // automatic Promise resolution value.
      // Run to the next yielded value...
      var next = it.next( value );  // generator result obj from the 1st yield
                                    // of form {value: value, done: t/f}
      return (function handleResult(next) { // Wrap in IIFE for error handling.
        // generator has completed running?
        if (next.done) {
          return next.value;
        }
        else { // Otherwise, deal with promisory...
          return Promise.resolve( next.value )
            .then(
              // resume the async loop on success, sending the resolved value
              // back into the generator
              handleNext,
              //
              // if `value` is a rejected promise, propagate error back into
              // the generator for its own error handling
              function handleErr(err) {
                return Promise.resolve(
                  it.throw( err )
                )
                .then( handleResult );
              }
            );
        }
      })(next);
    } );
}

run(main);

