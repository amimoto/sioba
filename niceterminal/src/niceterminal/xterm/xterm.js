export default {
  template: `<div class="p-0 m-0 bg-black"></div>`,
  props: {
    value: String,
    options: Object,
    resource_path: String,
  },
  data() {
    return {
      term: null,
      fitAddon: null,
    };
  },
  watch: {
    value(newValue) {
      if (this.term) {
        this.term.write(newValue);
      }
    },
  },
  methods: {
    async write(data) {
      // Note: No flow control done at the moment:
      // see https://xtermjs.org/docs/guides/flowcontrol/
      if (this.term) {
        const decoded = new TextDecoder().decode(
          Uint8Array.from(atob(data), c => c.charCodeAt(0))
        );
        this.term.write(decoded);
      }
    },
    refreshScreen(data) {
      if (this.term && !self.bufferInitialized) {
        self.bufferInitialized = true;
        this.write(data);
      }
    },
    setOption(name, value) {
      if (this.term) {
        // Ignore rows and cols
        if (value === null || value === undefined) {
          console.warn("Option value is undefined", name, value);
          return;
        }
        if (name === 'rows' || name === 'cols') {
          return;
        }
        this.term.options[name] = value;
      }
    },
    fit() {
      if (this.term && this.fitAddon) {
        this.fitAddon.fit();
      }
    },
    // From: https://github.com/zauberzeug/nicegui/discussions/1846#discussion-5758110
    callAPIMethod(name, ...args) {
      this.term[name](...args);
    },
    setCursorLocation(row, col) {
      if (this.term) {
        this.term.write(`\x1b[${row + 1};${col + 1}H`);
      }
    },
    rows() {
      return this.term.rows;
    },
    cols() {
      return this.term.cols;
    },
    focus() {
      this.term.focus();
    },
    noop() {
      // Do nothing
      return null;
    },

  },
  async mounted() {
    await this.$nextTick(); // Wait for window.path_prefix to be set

    // Dynamically import xterm.js and addons
    const {Terminal, FitAddon, SearchAddon, WebLinksAddon, AttachAddon, ClipboardAddon} = await import(window.path_prefix + `${this.resource_path}/xterm.js`);

    let options = {
      cursorBlink: true,
      cursorStyle: 'block',
      // fontSize: 16,
      fontFamily: 'monospace',
      allowProposedApi: true,
      charset: 'UTF-8',
      theme: {
        background: '#000000',
        foreground: '#FFFFFF',
      },
      ...this.options,
    }

    console.log(
      "Terminal options",
      options
    )

    this.term = new Terminal(options);
    this.fitAddon = new FitAddon();
    this.searchAddon = new SearchAddon();
    this.webLinksAddon = new WebLinksAddon();
    this.clibboardAddon = new ClipboardAddon();
    this.term.loadAddon(this.fitAddon);
    this.term.open(this.$el);
    this.bufferInitialized = false;

    // Handle terminal input
    this.term.onData((e) => {
      this.$emit('data', btoa(e), socket.id);
    });

    this.term.onKey((e) => {
      this.$emit('key', e, socket.id);
    });

    this.term.onBell((e) => {
      this.$emit('bell', e, socket.id);
    });

    this.term.onBinary((e) => {
      this.$emit('binary', e, socket.id);
    });

    this.term.onCursorMove((e) => {
      this.$emit('cursor_move', e, socket.id);
    });

    this.term.onLineFeed((e) => {
      this.$emit('line_feed', e, socket.id);
    });

    this.term.onRender((e) => {
      this.$emit('render', e, socket.id);
    });

    this.term.onResize((e) => {
      this.$emit('resize', e, socket.id)
    });

    this.term.onScroll((e) => {
      this.$emit('scroll', e, socket.id);
    });

    this.term.onTitleChange((e) => {
      this.$emit('title_change', e, socket.id);
    });

    this.term.onWriteParsed((e) => {
      this.$emit('write_parsed', e, socket.id);
    });

    // Write initial value
    if (this.value) {
      this.term.write(this.value);
    };

    // Initial fit
    this.fit();

    // Fit terminal on window resize
    window.addEventListener('resize', this.fit);
    this.term.onResize(this.fit);

    this.$emit('mount', {
      rows: this.term.rows,
      cols: this.term.cols
    }, socket.id);

    this.$emit('resize', {
      rows: this.term.rows,
      cols: this.term.cols
    }, socket.id);

    console.log("Terminal mounted", this.term.cols, this.term.rows, this);

    window.terminal = this.term; // For debugging purposes

  },
  beforeDestroy() {
    if (this.term) {
      this.term.dispose();
    }
    window.removeEventListener('resize', this.fit);
  },
};