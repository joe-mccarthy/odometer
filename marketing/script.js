'use strict';
const copyButton = document.querySelector('#copy');
const copyStatus = document.querySelector('#copy-status');
copyButton.addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(document.querySelector('#commands').textContent);
    copyButton.textContent = 'Copied!';
    copyStatus.textContent = 'Setup commands copied to clipboard.';
  } catch {
    copyButton.textContent = 'Select commands below';
    copyStatus.textContent = 'Clipboard unavailable. Select and copy the commands below.';
    const range = document.createRange();
    range.selectNodeContents(document.querySelector('#commands'));
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
  }
  window.setTimeout(() => { copyButton.textContent = 'Copy commands'; }, 3000);
});
