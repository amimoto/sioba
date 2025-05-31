const path = require('path');

module.exports = {
  entry: './src/index.js',
  output: {
    filename: 'xterm.mjs', // Use `.mjs` for ES module
    path: path.resolve(__dirname, 'dist'),
    library: {
      type: 'module', // Define as an ES module
    },
  },
  module: {
    rules: [
      {
        test: /\.css$/i,
        use: ['style-loader', 'css-loader'], // Handle CSS files
      },
    ],
  },
  experiments: {
    outputModule: true, // Enable ESM output
  },
  mode: 'production', // Set to 'development' for debugging
};
