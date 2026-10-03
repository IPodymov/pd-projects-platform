import { defineConfig, globalIgnores } from 'eslint/config'
import ts from 'typescript-eslint'
import vue from 'eslint-plugin-vue'
import vueParser from 'vue-eslint-parser'
import skipFormatting from 'eslint-config-prettier/flat'
export default defineConfig(
  globalIgnores(['**/dist/**','**/coverage/**']),
  ...ts.configs.recommended,
  ...vue.configs['flat/essential'],
  {files:['**/*.vue'],languageOptions:{parser:vueParser,parserOptions:{parser:ts.parser,extraFileExtensions:['.vue']}}},
  skipFormatting,
)
