'use strict';

const util = require('util');
const fs = require('fs');
const jsdom = require('jsdom').jsdom;
const squawker = require('./modules/squawker.js');

// Output from `consolidate-lists.py` script
const master_list = require('./lists/union_katex_lshort.json');
const outfile = 'lists/update_asm_mj.json';
if (typeof __dirname === 'undefined')
  var __dirname = process.cwd();

var dummy = fs.readFileSync(`${__dirname}/dummy.html`, 'utf-8');
var document = jsdom(dummy);
var window = document.defaultView;
var VERBOSE = true;
var LOGMAX = 'info';
var squawk = squawker(LOGMAX, VERBOSE);
var MathJax;

var force_mode = {'implies':['math'], 'impliedby':['math'],
                  'underparen':['math']};

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

function check_DOM_loaded() {
  return new Promise(
    function _check_DOM_loaded_prom_cb(resolve) {
      document.addEventListener('DOMContentLoaded', function(event) {
        squawk(`DOM fully loaded and parsed: ${event}`);
      });
      window.addEventListener('load', function(event) {
        squawk(`Event "load" done: ${event}`);
        squawk(`document.readyState: ${document.readyState}`);
        resolve(window.MathJax);
      });
    }
  );
}

function do_q(fn_arr, msg) {
  return new Promise( function _do_q_prom_cb(resolve) {
    function cb(x) {
      resolve(x);
    }
    MathJax.Hub.Queue([...fn_arr, cb(msg) ]);
  });
}

function subscribe_debug_signals(msg) {
  //  Echo all startup and hub messages to stdout. Consider moving to
  //  `./dummy_load.js` like those for error messages...
  MathJax.Hub.Startup.signal.Interest(
    function _Interest(message) {
      squawk(`Startup: ${message}`);
    }
  );
  //
  MathJax.Hub.signal.Interest(
    function _Interest(message) {
      squawk(`Hub: ${message}`);
    }
  );
  return Promise.resolve(msg);
}

function register_startup_hook(listen_msg, retv, ignorePast=true) {
  // Consider changing ignorePast default to false, safer...
  return new Promise(function _register_startup_hook(resolve) {
    if ( ignorePast )
      MathJax.Hub.Register.StartupHook( listen_msg, [ resolve, retv ]);
    else
      MathJax.Hub.Startup.signal.Interest(
        function _startupHook_past(msg) {
          ( msg[0] === listen_msg ) &&
            resolve(retv);
        }
      );
  });
}

function register_hub_hook(listen_msg, retv, ignorePast=true) {
  // Consider changing ignorePast default to false, safer...
  return new Promise(function _register_hub_hook(resolve) {
    if ( ignorePast )
      MathJax.Hub.Register.MessageHook( listen_msg, [ resolve, retv ]);
    else
      MathJax.Hub.signal.Interest(
        function _hubHook_past(msg) {
          if ( msg[0] === listen_msg ) {
            resolve(retv);
          }
        }
      );
  });
}

function getMathML(jax, cb) {
  let mml;
  try {
    mml = jax.root.toMathML('');
  } catch(err) {
    if (!err.restart)
      throw err;
    return MathJax.Callback.After([getMathML, jax, cb], err.restart);
  }
  MathJax.Callback(cb)(mml);
}

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
      resolve(`Wrote ${out_name}`);
    });
  });
}

function* do_trivial() { // eslint-disable-line no-unused-vars
  // Continuation of `main()` for exploring typesetting with jsdom, which seems
  // pretty pointless... So far, typesetting produces errors, and `.getJaxFor`
  // method fails. Might be related to `<pre>` tag failure and/or handful of
  // error warnings in debug log...
  //
  // Important takeaway from docs: instead of this, which returns inscrutable
  // span of `<span>`s...
  /*
   * let myEl = document.getElementById('myElement');
   * squawk(myEl.innerHTML, 6);
   * // Mutate element, then request update...
   * myEl.textContent = '\x24\x5cexists\x24';
   * // Use "method syntax" for Callback Object otherwise `this` is not bound...
   * squawk(yield do_q(['Typeset', MathJax.Hub, myEl], 'Changed element'), 6);
   * squawk(myEl.innerHTML, 6);
   */
  // ... Do this:
  let [myElJax, ,] = MathJax.Hub.getAllJax('myElement');
  // Get existing ML for element...
  squawk(yield do_q( [getMathML, myElJax,
                      (mml) => { squawk( `Before\n: ${mml}`, 6 ); }],
                      'Queued a "toMathML" call'), 6);
  // Instead, let built-in `MathJax.ElementJax.Text()` method handle update...
  squawk(yield do_q( ['Text', myElJax, '\x24\x5cexists\x24'],
                     'Changed element' ), 6);
  // Get updated rendering...
  squawk(yield do_q( [getMathML, myElJax,
                      (mml) => { squawk( `After\n: ${mml}`, 6 ); }],
                      'Queued another "toMathML" call' ), 6);
}

function* main() {
  //
  // Start stopwatch for logger
  // Initialize MathJax namespace in global scope...
  MathJax = yield check_DOM_loaded();
  // This is just a dumb list of passive hooks to register for debugging...
  squawk(yield subscribe_debug_signals('Subscribed to debug signals'), 6);
  // While these "register hooks" helper funcs are explicitly for yielding
  // promises, they'll hang execution if message has already passed and
  // won't come around again. If unsure, pass `false` option. That said...
  squawk(yield register_startup_hook('End Extensions',
                                      'Setup complete', true),  6);
  squawk(`"MathJax.isReady": ${MathJax.isReady}`,  6);
  squawk(yield register_hub_hook('End Math Input',
                                  'PreProcessing complete', false),  6);
  squawk(`InputJax ready?: ${MathJax.InputJax.hasOwnProperty('TeX')}`, 5);
  //
  // Get lists of TeX Definitions...
  let tex_defs = MathJax.InputJax.TeX.Definitions;
  // Exclude delimeters (only `.` matches) and special (useless) cats...
  let tex_defs_keys = Object.getOwnPropertyNames(tex_defs).filter(
    (key) => key.search(/^math|^mac|^env/) >= 0
  );
  // Could also iter through master_list w. `cmd.replace(/^[\\]+/, '')`, but
  // this seems easier to manage...
  for (let cat of tex_defs_keys) {
    for (let cmd of Object.getOwnPropertyNames(tex_defs[cat])) {
      let cmd_full = '\\' + cmd;
      if (cmd.search(/^\s+$|^\xa0$/ ) >= 0 ||
          cmd.length < 2
      ) continue;
      else if (cmd in master_list || cmd_full in master_list) {
        for (let c of [cmd, cmd_full]) {
          if (!(c in master_list))
            continue;
          else if (master_list[c]['meta'] !== null)
            master_list[c]['meta']['mathjax'] = true;
          else
              master_list[c]['meta'] = {'mathjax': true};
        }
      } else {
        let sym = null;
        if (cat.startsWith('math')) {
          sym = typeof tex_defs[cat][cmd] === 'object' ?
                tex_defs[cat][cmd][0] : tex_defs[cat][cmd];
          sym = String.fromCodePoint( Number('0x' + sym) );
        }
        //
        let template = {
          type: cat.startsWith('math') || cat === 'macros' ? 'command' : cat,
          meta: {'mathjax': true},
          name: cat === 'environment' ? cmd : '\\' + cmd,
          symbol: sym,
          // Need smarter way to sort macros (some don't belong in both modes)
          mode: cmd in force_mode ? force_mode[cmd] :
                cat === 'macros' ? ['math', 'text'] : ['math']
        };
        squawk(`${cat}: ${cmd} --> ${tex_defs[cat][cmd]}`, 7);
        squawk(`${template.name}: ${util.inspect(template)}`, 7);
        // Append entry to master_list
        master_list[template.name] = template;
      }
    }
  }
  // Async tasks are still pending, but they take up to a minute to complete.
  // This is doubtless related to the hackiness of running mathjax without a
  // browser. Instead, just write updated list and exit immediately.

  if (yield* move_existing(outfile)) {
    squawk(yield save_updated_list(outfile), 5);
  }
  process.exit(0);
  //
  /*
   * // If typesetting, need to wait for first pass to complete:
   * squawk(yield register_startup_hook('End', 'Initial typesetting complete',
   *                                     true),  6);
   * // Actual work done, okay to mess around...
   * yield* do_trivial();
   */
  //
}

run(main);

// ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
// DEBUG SLUG  ****************************************************************
// ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
