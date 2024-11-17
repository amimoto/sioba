import { Terminal } from 'xterm';
import { FitAddon } from '@xterm/addon-fit';
import { SearchAddon } from '@xterm/addon-search';
import { WebLinksAddon } from '@xterm/addon-web-links';
import { AttachAddon } from '@xterm/addon-attach';
import { ClipboardAddon } from '@xterm/addon-clipboard';
import 'xterm/css/xterm.css';

// Export Terminal and Addon classes
export { Terminal, FitAddon, SearchAddon, WebLinksAddon, AttachAddon, ClipboardAddon };

// Export a utility function to initialize the terminal
export function createTerminal(container) {
  const terminal = new Terminal();
  terminal.open(container);
  return terminal;
}

console.log("Loaded xterm.js extension");