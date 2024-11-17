const path = require('path');

module.exports = {
  entry: './src/index.js', // Entry point
  output: {
    filename: 'xterm-library.js', // Output file
    path: path.resolve(__dirname, 'dist'), // Output directory
    library: 'XtermLibrary', // Global variable for the library
    libraryTarget: 'umd', // Universal Module Definition
  },
  module: {
    rules: [
      {
        test: /\.css$/i,
        use: ['style-loader', 'css-loader'], // Process CSS files
      },
    ],
  },
  optimization: {
    minimize: true, // Ensures minification
  },
  mode: 'production', // Set to 'development' for debugging
};

