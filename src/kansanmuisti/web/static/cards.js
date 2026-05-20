// Keräilykortit: klikkaus kääntää kortin, holo-kiilto seuraa kursoria.
(function () {
  function onClick(e) {
    var card = e.target.closest('.tcard');
    if (!card) return;
    if (e.target.closest('a')) return;        // anna linkkien toimia
    card.classList.toggle('flipped');
  }
  function onMove(e) {
    var card = e.target.closest('.tcard');
    if (!card) return;
    var r = card.getBoundingClientRect();
    card.style.setProperty('--mx', ((e.clientX - r.left) / r.width * 100) + '%');
    card.style.setProperty('--my', ((e.clientY - r.top) / r.height * 100) + '%');
  }
  function onKey(e) {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    var card = e.target.closest && e.target.closest('.tcard');
    if (card) { e.preventDefault(); card.classList.toggle('flipped'); }
  }
  document.addEventListener('click', onClick);
  document.addEventListener('pointermove', onMove);
  document.addEventListener('keydown', onKey);
})();
