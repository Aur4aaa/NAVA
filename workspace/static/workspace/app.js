(() => {
  const body = document.body;
  const toggle = document.querySelector('[data-toggle-sidebar]');
  const overlay = document.querySelector('[data-close-sidebar]');
  function setMenu(open) {
    body.classList.toggle('sidebar-open', open);
    if (toggle) toggle.setAttribute('aria-expanded', String(open));
    if (overlay) overlay.hidden = !open;
  }
  toggle?.addEventListener('click', () => setMenu(!body.classList.contains('sidebar-open')));
  overlay?.addEventListener('click', () => setMenu(false));
  document.querySelectorAll('[data-dismiss-message]').forEach(button => button.addEventListener('click', () => button.closest('.toast').remove()));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      setMenu(false);
      document.querySelectorAll('details[open]').forEach(details => details.open = false);
    }
    if (event.key === '/' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName) && !document.activeElement.isContentEditable) {
      const input = document.querySelector('.global-search input');
      if (input) { event.preventDefault(); input.focus(); }
    }
  });
  document.querySelectorAll('[data-confirm]').forEach(form => form.addEventListener('submit', event => {
    if (!window.confirm(form.dataset.confirm)) event.preventDefault();
  }));
  document.querySelectorAll('.record-form input[type="file"]').forEach(input => input.addEventListener('change', () => {
    const note = input.closest('.form-field').querySelector('[data-file-name]');
    if (note) note.textContent = input.files.length ? input.files[0].name : '';
  }));
})();
