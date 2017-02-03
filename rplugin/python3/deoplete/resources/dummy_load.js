
/* eslint-disable */

MathJax.Hub.Config({
  tex2jax: {inlineMath: [["$","$"],["\(","\)"]]},
  extensions: ["toMathML.js"]
});

MathJax.Hub.Register.MessageHook(
  'Math Processing Error',
  function _MessageHook_cb(message) {
    console.error(message[2]);
  }
);

MathJax.Hub.Register.MessageHook(
  'TeX Jax - parse error',
  function _MessageHook_cb(message) {
    console.error(message[1]);
  }
);

MathJax.Hub.Register.LoadHook(
  "[MathJax]/extensions/TeX/noUndefined.js",
  function _LoadHook_cb() {
    MathJax.Hub.Startup.signal.Post("*** noUndefined Loaded ***");
  }
);

MathJax.Hub.Register.LoadHook(
  "[MathJax]/extensions/TeX/AMSmath.js",
  function _LoadHook_cb() {
    MathJax.Hub.Startup.signal.Post("*** AMSmath Loaded ***")
  }
);

MathJax.Hub.Register.LoadHook(
  "[MathJax]/extensions/toMathML.js",
  function _LoadHook_cb() {
    MathJax.Hub.Startup.signal.Post("*** toMathML Loaded ***");
  }
);

MathJax.Hub.Startup.signal.Post("*** In Startup Configuration code ***");

MathJax.Hub.Register.StartupHook(
  "onLoad",
  function _StartupHook_cb() {
    console.log("*** The onLoad handler has run,",
      "page is ready to process ***");
  }
);

MathJax.Hub.Queue(function _Queue_cb() {
  console.log("*** MathJax is done ***")
  }
);


MathJax.Ajax.loadComplete("[MathJax]/config/../../../dummy_load.js");

