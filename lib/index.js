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
 * DSH upgrade.
 */

import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { buildPresetPlugins } from './preset.js';
import { createProvider, PROVIDER_NAME } from './skill-provider.js';

const PACKAGE_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');

/** The CNKI MCP server ships inside this package; its path is resolved here. */
const CNKI_DIR = join(PACKAGE_ROOT, 'servers', 'cnki-search');

export const PRESET_ID = 'academic';

/**
 * Build the academic preset definition.
 * @param {string} cnkiDir - absolute path of the bundled CNKI server.
 * @returns {object} a PresetDefinition.
 */
export function buildPresetDefinition(cnkiDir = CNKI_DIR) {
  return {
    id: PRESET_ID,
    name: '学术研究',
    description: '文献检索、综述与学术写作的研究助手',
    order: 0,
    plugins: buildPresetPlugins({ cnkiDir }),
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
