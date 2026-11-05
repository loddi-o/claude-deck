# Third-party notices

Claude Deck itself is MIT licensed (see [LICENSE](LICENSE)). It ships or bundles the following third-party
software, each under its own license.

## whisper.cpp — `bin/whisper-cli`

`bin/whisper-cli` is `whisper-cli` built from [whisper.cpp](https://github.com/ggml-org/whisper.cpp)
(release v1.9.5) with `scripts/build-whisper.sh`. whisper.cpp (including ggml) is distributed under the MIT license:

```
MIT License

Copyright (c) 2023-2026 The ggml authors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

The speech recognition models are not included: they are downloaded on first use from
`https://huggingface.co/ggerganov/whisper.cpp`.

## Bundled into `dist/index.js` (the frontend)

| Package | Version | License |
|---|---|---|
| `@decky/api` | 1.1.3 | LGPL-2.1 |
| `react-icons` | 5.7.0 | MIT |

- The icons used come from `react-icons/fa`, i.e. **Font Awesome Free 5** (https://fontawesome.com),
  licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Icons by Font Awesome.
- `@decky/ui` (LGPL-2.1) is not bundled: Decky Loader provides it at runtime. React is provided by Steam.
- The complete source of this plugin, including the build scripts, is in this repository.

## Build-time only (not shipped)

Node.js, pnpm, Rollup (`@decky/rollup`, BSD-3-Clause), TypeScript, Vitest, esbuild.

"Claude" is a trademark of Anthropic and "Steam" / "Steam Deck" are trademarks of Valve. This project is
not affiliated with or endorsed by either company.
