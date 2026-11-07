/**
 * Skill provider that serves the `download-paper` skill shipped inside this
 * package.
 *
 * The provider object is the plain interface `ctx.skills` accepts: `list`
 * returns the candidate summaries, `get` loads one body. `SKILL.md` is re-read
 * on every call so edits show up without a restart.
 *
 * @module dsh-scholar-digest/skill-provider
 */

import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

/** Precedence rank packaged skill providers use (matches `dsh-skill`). */
const PACKAGED_SKILL_RANK = 600;

/** Public skill-name grammar: lowercase kebab-case. */
const SKILL_NAME_RE = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

export const PROVIDER_NAME = 'dsh-scholar-digest';

const PACKAGE_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const SKILL_DIR = join(PACKAGE_ROOT, 'skills', 'download-paper');
const SKILL_FILE = join(SKILL_DIR, 'SKILL.md');

/**
 * Parse the scalar `key: value` frontmatter a `SKILL.md` uses.
 * @param {string} text - raw file contents.
 * @returns {{ attrs: Record<string, string>, body: string }} parsed parts.
 */
export function parseFrontmatter(text) {
  const clean = String(text).replace(/^\uFEFF/, '');
  const match = /^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/.exec(clean);
  if (!match) return { attrs: {}, body: clean };

  /** @type {Record<string, string>} */
  const attrs = {};
  for (const line of match[1].split(/\r?\n/)) {
    const pair = /^([A-Za-z0-9_-]+)\s*:\s*(.*)$/.exec(line);
    if (!pair) continue;
    let value = pair[2].trim();
    const quoted =
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"));
    if (quoted && value.length >= 2) value = value.slice(1, -1);
    attrs[pair[1]] = value;
  }
  return { attrs, body: clean.slice(match[0].length) };
}

/**
 * Read the bundled skill into a provider candidate.
 * @param {(message: string) => void} warn - warning sink.
 * @returns {object | undefined} candidate, or `undefined` when unusable.
 */
function readCandidate(warn) {
  let parsed;
  try {
    parsed = parseFrontmatter(readFileSync(SKILL_FILE, 'utf8'));
  } catch (error) {
    warn(`cannot read ${SKILL_FILE}: ${error.message}`);
    return undefined;
  }

  const name = String(parsed.attrs.name || '').trim();
  if (!SKILL_NAME_RE.test(name)) {
    warn(`skipping bundled skill: name must be kebab-case, got ${JSON.stringify(parsed.attrs.name)}`);
    return undefined;
  }
  const description = String(parsed.attrs.description || '').trim();
  if (!description) {
    warn(`skipping ${name}: description is required`);
    return undefined;
  }

  /** A skill whose frontmatter opts out of model invocation stays user-only. */
  const modelInvocable = parsed.attrs['disable-model-invocation'] !== 'true';
  const userInvocable = parsed.attrs['user-invocable'] !== 'false';

  return {
    name,
    description,
    invocation: { modelInvocable, userInvocable },
    source: 'bundled',
    provider: PROVIDER_NAME,
    path: SKILL_FILE,
    resourceBase: { kind: 'directory', path: SKILL_DIR },
    rank: PACKAGED_SKILL_RANK,
    locator: SKILL_FILE,
  };
}

/**
 * Create the provider registered on `ctx.skills`.
 * @param {(message: string) => void} [warn] - warning sink.
 * @returns {{ name: string, list: Function, get: Function }} provider object.
 */
export function createProvider(warn = () => {}) {
  return {
    name: PROVIDER_NAME,

    /**
     * List the bundled skill.
     * @param {{ signal?: AbortSignal }} [lookup] - lookup options.
     * @returns {Promise<object[]>} candidate summaries.
     */
    async list(lookup) {
      if (lookup?.signal?.aborted) return [];
      const candidate = readCandidate(warn);
      return candidate ? [candidate] : [];
    },

    /**
     * Load the bundled skill body.
     * @param {object} candidate - candidate returned by `list`.
     * @param {{ signal?: AbortSignal }} [lookup] - lookup options.
     * @returns {Promise<object | undefined>} full definition, or `undefined`.
     */
    async get(candidate, lookup) {
      if (lookup?.signal?.aborted) return undefined;
      let parsed;
      try {
        parsed = parseFrontmatter(readFileSync(candidate.locator, 'utf8'));
      } catch (error) {
        warn(`cannot load ${candidate.name}: ${error.message}`);
        return undefined;
      }
      return { ...candidate, content: parsed.body.replace(/^\s*\n/, '') };
    },
  };
}
