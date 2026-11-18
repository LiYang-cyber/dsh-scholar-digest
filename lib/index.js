/**
 * dsh-scholar-digest — academic research preset plus the download-paper skill.
 *
 * The bundle contributes two things through the Host:
 *  - a skill provider serving `skills/download-paper/SKILL.md`, so the skill is
 *    in the agent catalog as soon as the plugin is installed;
 *  - the `academic` agent preset (persona, tool set, and the literature MCP
 *    servers), mounted through `ctx.agentPresets`.
 *
 * The preset rows are generated from the installed DSH's `preset-standard`
 * (see lib/preset.js) so a hand-copied plugin list cannot silently rot after a
 * DSH upgrade. Paths are resolved here, at runtime:
 *  - the CNKI server shipped inside this package (override: DSH_CNKI_DIR);
 *  - the optional nature-academic-search server, detected under
 *    `$DSH_HOME/skills/nature-academic-search/mcp-server` (override:
 *    DSH_ACADEMIC_SEARCH_DIR); its row and its persona mention only exist when
 *    the server is found;
 *  - the user skill root `$DSH_HOME/skills`.
 */

import { existsSync } from 'node:fs';
import { homedir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { buildPresetPlugins } from './preset.js';
import { createProvider, PROVIDER_NAME } from './skill-provider.js';

const PACKAGE_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');

export const DSH_HOME = process.env.DSH_HOME ?? join(homedir(), '.dsh');

/** The CNKI MCP server ships inside this package; its path is resolved here. */
export const CNKI_DIR = process.env.DSH_CNKI_DIR ?? join(PACKAGE_ROOT, 'servers', 'cnki-search');

/** The user skill root the preset registers on skill-filesystem. */
export const SKILL_DIR = join(DSH_HOME, 'skills');

/** Agent preset identity this bundle registers. */
export const PRESET_ID = 'academic';

/**
 * Locate the optional nature-academic-search MCP server.
 * @returns {string | undefined} its `mcp-server` directory, or undefined.
 */
export function resolveAcademicSearchDir() {
  const explicit = process.env.DSH_ACADEMIC_SEARCH_DIR;
  if (explicit) return explicit;
  const candidate = join(DSH_HOME, 'skills', 'nature-academic-search', 'mcp-server');
  return existsSync(join(candidate, 'academic_search_server.py')) ? candidate : undefined;
}

/**
 * Path of the interpreter inside a server directory's `.venv`.
 * @param {string | undefined} dir - server directory.
 * @returns {string | undefined} interpreter path, or undefined for no directory.
 */
export function academicSearchPython(dir) {
  if (!dir) return undefined;
  return process.platform === 'win32'
    ? join(dir, '.venv', 'Scripts', 'python.exe')
    : join(dir, '.venv', 'bin', 'python');
}

/**
 * Add the academic-search tool to the persona's tool list.
 * @param {object[]} rows - mutable preset rows.
 */
function mentionAcademicSearch(rows) {
  const persona = rows.find((row) => row?.id === 'persona');
  const prefix = persona?.config?.prefix;
  if (typeof prefix !== 'string' || prefix.includes('mcp__academic-search__*')) return;
  persona.config.prefix = prefix.replace(
    'mcp__semantic-scholar__*,',
    'mcp__semantic-scholar__*, mcp__academic-search__*,',
  );
}

/**
 * Build the academic preset definition.
 * @param {object} [options] - path overrides, mostly for tests.
 * @param {string} [options.cnkiDir] - bundled CNKI server directory.
 * @param {string} [options.skillDir] - user skill root.
 * @param {string | undefined} [options.academicSearchDir] - nature-academic-search server.
 * @returns {object} a PresetDefinition.
 */
export function buildPresetDefinition({
  cnkiDir = CNKI_DIR,
  skillDir = SKILL_DIR,
  academicSearchDir,
} = {}) {
  // Omitted means "detect"; an explicit value (including null) wins, so tests
  // and embedders can disable the optional server.
  const serverDir =
    academicSearchDir === undefined ? resolveAcademicSearchDir() : academicSearchDir;
  const rows = buildPresetPlugins({
    cnkiDir,
    skillDir,
    academicSearchDir: serverDir ?? '',
    academicSearchPython: academicSearchPython(serverDir) ?? '',
  });
  if (serverDir) mentionAcademicSearch(rows);
  const plugins = serverDir
    ? rows
    : rows.filter((row) => row?.id !== 'mcp-academic-search');
  return {
    id: PRESET_ID,
    name: '学术研究',
    description: '文献检索、综述与学术写作的研究助手',
    order: 0,
    plugins,
  };
}

/**
 * Register the bundled skill provider and the academic preset on the Host.
 * @param {object} ctx - Cordis context of this plugin.
 */
export function apply(ctx) {
  const warn = (message) => {
    try {
      const logger = typeof ctx?.logger === 'function' ? ctx.logger(PROVIDER_NAME) : ctx?.logger;
      if (logger && typeof logger.warn === 'function') {
        logger.warn(message);
        return;
      }
    } catch {
      /* fall through to the console */
    }
    try {
      console.warn(`[${PROVIDER_NAME}] ${message}`);
    } catch {
      /* nothing left to report to */
    }
  };

  ctx.inject(['skills'], (skillCtx) => {
    skillCtx.skills.registerProvider(() => createProvider(warn));
  });

  ctx.inject(['agentPresets'], (presetCtx) => {
    presetCtx.effect(() => {
      let disposed = false;
      let unregister;
      presetCtx.agentPresets
        .register(buildPresetDefinition())
        .then((dispose) => {
          unregister = dispose;
          if (disposed) void dispose();
        })
        .catch((error) => {
          warn(`cannot register the academic preset: ${error?.message ?? error}`);
        });
      return async () => {
        disposed = true;
        if (unregister) await unregister();
      };
    }, 'dsh-scholar-digest.preset');
  });
}
