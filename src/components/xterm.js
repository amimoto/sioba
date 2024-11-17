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
      if (this.term) {
        this.term.write(data);
      }
    },
    fit() {
      if (this.term && this.fitAddon) {
        this.fitAddon.fit();
      }
    },
  },
  async mounted() {
    await this.$nextTick(); // Wait for window.path_prefix to be set

    // Dynamically import xterm.js and addons
    const {Terminal, FitAddon, SearchAddon, WebLinksAddon, AttachAddon, ClipboardAddon } = await import(window.path_prefix + `${this.resource_path}/xterm.js`);

    this.term = new Terminal(this.options);
    this.fitAddon = new FitAddon();
    this.term.loadAddon(this.fitAddon);
    this.term.open(this.$el);

    // Initial fit
    this.fit();

    // Handle terminal input
    this.term.onData((data) => {
      this.$emit('input', data);
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