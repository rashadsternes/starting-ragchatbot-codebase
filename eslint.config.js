export default [
  {
    files: ['frontend/**/*.js'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'script',
      globals: {
        console: 'readonly',
        document: 'readonly',
        window: 'readonly',
        fetch: 'readonly',
        marked: 'readonly',
        Date: 'readonly',
      },
    },
    rules: {
      indent: ['error', 2],
      'linebreak-style': ['error', 'unix'],
      quotes: ['error', 'single'],
      semi: ['error', 'always'],
      'no-unused-vars': 'warn',
      'no-console': 'off',
      'no-undef': 'error',
    },
  },
  {
    ignores: [
      'node_modules/',
      'backend/',
      'dist/',
      'build/',
      'chroma_db/',
      '*.py',
      '*.log',
    ],
  },
];
