/* Handoff copy: loads the design system's stylesheet as a sibling file so both
   HTML prototypes open standalone from this folder. In the original project this
   file resolves ../../styles.css and also loads the compiled component bundle;
   neither prototype uses a compiled component, so the bundle is omitted here. */
(() => {
  const l = document.createElement('link');
  l.rel = 'stylesheet'; l.href = './styles.css';
  document.head.appendChild(l);
})();
