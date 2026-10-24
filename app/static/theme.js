'use strict';
// Tema claro/escuro: a escolha fica salva neste navegador; sem escolha, segue o sistema.
(() => {
  const root = document.documentElement;
  const system = matchMedia('(prefers-color-scheme: dark)');
  let chosen = null;
  try {
    chosen = localStorage.getItem('eppgg.theme');
  } catch {
    /* armazenamento indisponível: segue o sistema */
  }
  const apply = () => {
    root.dataset.theme = chosen || (system.matches ? 'dark' : 'light');
  };
  apply();
  system.addEventListener('change', () => chosen || apply());
  window.toggleTheme = () => {
    chosen = root.dataset.theme === 'dark' ? 'light' : 'dark';
    try {
      localStorage.setItem('eppgg.theme', chosen);
    } catch {
      /* a escolha vale só para esta visita */
    }
    apply();
  };
})();
