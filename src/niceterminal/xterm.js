export default {
  template: `
    <div></div>
  `,
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
    write(data) {
      // Note: No flow control done at the moment:
      // see https://xtermjs.org/docs/guides/flowcontrol/
      if (this.term) {
        this.term.write(data);
      }
    },
    fit() {
      if (this.term && this.fitAddon) {
        this.fitAddon.fit();
      }
    },
    // From: https://github.com/zauberzeug/nicegui/discussions/1846#discussion-5758110
    call_api_method(name, ...args) {
      this.term[name](...args);
    },
    rows() {
      return this.term.rows;
    },
    cols() {
      return this.term.cols;
    },

  },
  async mounted() {
    await this.$nextTick(); // Wait for window.path_prefix to be set

    // Dynamically import xterm.js and addons
    const {Terminal, FitAddon, SearchAddon, WebLinksAddon, AttachAddon, ClipboardAddon } = await import(window.path_prefix + `${this.resource_path}/xterm.js`);

    this.term = new Terminal(this.options);
    this.fitAddon = new FitAddon();
    this.searchAddon = new SearchAddon();
    this.webLinksAddon = new WebLinksAddon();
    this.clibboardAddon = new ClipboardAddon();
    this.term.loadAddon(this.fitAddon);
    this.term.open(this.$el);

    // Initial fit
    this.fit();

    console.log("Terminal mounted", this.term.cols, this.term.rows);

    // Handle terminal input
    this.term.onData((data) => {
      this.$emit('input', data);
    });

    this.term.onKey((e) => {
      this.$emit('key', e);
    });

    this.term.onBell((e) => {
      this.$emit('bell', e);
    });

    this.term.onBinary((e) => {
      this.$emit('binary', e);
    });

    this.term.onCursorMove((e) => {
      this.$emit('cursor_move', e);
    });

    this.term.onLineFeed((e) => {
      this.$emit('line_feed', e);
    });

    this.term.onRender((e) => {
      this.$emit('render', e);
    });

    this.term.onResize((e) => {
      console.log("EMIT resize", e);
      this.$emit('resize', e);
    });

    this.term.onScroll((e) => {
      this.$emit('scroll', e);
    });

    this.term.onTitleChange((e) => {
      this.$emit('title_change', e);
    });

    this.term.onWriteParsed((e) => {
      this.$emit('write_parsed', e);
    });

    // Write initial value
    if (this.value) {
      this.term.write(this.value);
    }

    // Fit terminal on window resize
    window.addEventListener('resize', this.fit);
  },
  beforeDestroy() {
    if (this.term) {
      this.term.dispose();
    }
    window.removeEventListener('resize', this.fit);
  },
};