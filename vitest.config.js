import path from 'path'

export default {
  test: {
    environment: 'node',
    globals: true,
  },
  resolve: {
    alias: {
      '@': path.resolve(new URL('.', import.meta.url).pathname),
    },
  },
}
