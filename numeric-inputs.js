// Keep numeric validation, but require deliberate typing to change a value.
(() => {
  const isNumberInput = (target) => target instanceof HTMLInputElement && target.type === 'number';

  document.addEventListener('wheel', (event) => {
    if (isNumberInput(event.target) && event.target === document.activeElement) {
      event.preventDefault();
    }
  }, { capture: true, passive: false });

  document.addEventListener('keydown', (event) => {
    if (isNumberInput(event.target) && (event.key === 'ArrowUp' || event.key === 'ArrowDown')) {
      event.preventDefault();
    }
  }, true);
})();
