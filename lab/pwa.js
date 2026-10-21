(() => {
  'use strict';
  const installButton = document.getElementById('installApp');
  const dialog = document.getElementById('installDialog');
  const confirmButton = document.getElementById('confirmInstall');
  const instructions = document.getElementById('installInstructions');
  const result = document.getElementById('installResult');
  const standalone = window.matchMedia('(display-mode: standalone)');
  let installPrompt = null;
  let waitingWorker = null;
  let updateRequested = false;

  const installed = () => standalone.matches || navigator.standalone === true;
  const updateInstallButton = () => { installButton.hidden = installed(); };
  updateInstallButton();
  standalone.addEventListener('change', updateInstallButton);

  window.addEventListener('beforeinstallprompt', event => {
    event.preventDefault();
    installPrompt = event;
    confirmButton.hidden = false;
    instructions.textContent = 'Dodirni „Instaliraj Trend Birth” i potvrdi instalaciju.';
    updateInstallButton();
  });
  window.addEventListener('appinstalled', () => {
    installPrompt = null;
    confirmButton.hidden = true;
    installButton.hidden = true;
    dialog.close();
  });
  installButton.addEventListener('click', () => {
    result.textContent = '';
    if (!installPrompt) {
      const ios = /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
      instructions.textContent = ios
        ? 'Otvori ovu stranicu u Safariju. Dodirni Dijeli → Dodaj na početni zaslon → Dodaj.'
        : 'Otvori ovu stranicu u Chromeu. U izborniku ⋮ odaberi „Dodaj na početni zaslon” ili „Instaliraj aplikaciju” i potvrdi. Ako si u Telegramu ili drugoj aplikaciji, prvo odaberi „Otvori u Chromeu”.';
      confirmButton.hidden = true;
    }
    dialog.showModal();
  });
  confirmButton.addEventListener('click', async () => {
    if (!installPrompt) return;
    const prompt = installPrompt;
    installPrompt = null;
    confirmButton.disabled = true;
    try {
      await prompt.prompt();
      const choice = await prompt.userChoice;
      result.textContent = choice.outcome === 'accepted'
        ? 'Instalacija je potvrđena. Potraži ikonu Trend Birth na početnom zaslonu ili među aplikacijama.'
        : 'Instalacija je otkazana. Možeš je ponovno pokrenuti iz izbornika preglednika.';
    } catch {
      result.textContent = 'Instalaciju pokreni iz izbornika preglednika: Dodaj na početni zaslon.';
    } finally {
      confirmButton.disabled = false;
      confirmButton.hidden = true;
    }
  });
  const updateConnection = () => { document.getElementById('connectionNotice').hidden = navigator.onLine; };
  window.addEventListener('online', updateConnection);
  window.addEventListener('offline', updateConnection);
  updateConnection();

  if (!('serviceWorker' in navigator)) return;
  const showUpdate = worker => {
    waitingWorker = worker;
    document.getElementById('updateNotice').hidden = false;
  };
  document.getElementById('updateApp').addEventListener('click', () => {
    if (!waitingWorker) return;
    updateRequested = true;
    waitingWorker.postMessage({type: 'ACTIVATE_UPDATE'});
  });
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (updateRequested) window.location.reload();
  });
  navigator.serviceWorker.register('./sw.js', {updateViaCache: 'none'}).then(registration => {
    if (registration.waiting && navigator.serviceWorker.controller) showUpdate(registration.waiting);
    registration.addEventListener('updatefound', () => {
      const worker = registration.installing;
      worker?.addEventListener('statechange', () => {
        if (worker.state === 'installed' && navigator.serviceWorker.controller) showUpdate(worker);
      });
    });
  }).catch(() => { /* Review and manual installation remain usable. */ });
})();
