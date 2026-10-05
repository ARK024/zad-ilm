/**
 * Zad Al-Ilm - Anki Template & Cloze Deletion Engine
 * Implements Mustache-like parsing, Cloze deletion, conditionals, and audio tags.
 */

const AnkiTemplateEngine = (() => {
  /**
   * Renders an Anki template string using fields and cloze options
   */
  const render = (template, fields = {}, clozeOrd = 1, isAnswer = false, renderedFront = '') => {
    if (!template) return '';
    let output = template;

    // 1. Handle {{FrontSide}} on back template
    if (isAnswer) {
      output = output.replace(/\{\{FrontSide\}\}/g, renderedFront || '');
    } else {
      output = output.replace(/\{\{FrontSide\}\}/g, '');
    }

    // 2. Conditionals: {{#Field}} content {{/Field}}
    output = output.replace(/\{\{#([^}]+)\}\}([\s\S]*?)\{\{\/\1\}\}/g, (match, fieldName, content) => {
      const val = (fields[fieldName.trim()] || '').trim();
      return val ? content : '';
    });

    // 3. Inverted Conditionals: {{^Field}} content {{/Field}}
    output = output.replace(/\{\{\^([^}]+)\}\}([\s\S]*?)\{\{\/\1\}\}/g, (match, fieldName, content) => {
      const val = (fields[fieldName.trim()] || '').trim();
      return !val ? content : '';
    });

    // 4. Cloze Deletion: {{cloze:FieldName}}
    output = output.replace(/\{\{cloze:([^}]+)\}\}/g, (match, fieldName) => {
      const text = fields[fieldName.trim()] || '';
      return processCloze(text, clozeOrd || 1, isAnswer);
    });

    // 5. Field Replacements: {{FieldName}}
    for (const [key, value] of Object.entries(fields)) {
      const regex = new RegExp(`\\{\\{${escapeRegex(key)}\\}\\}`, 'g');
      output = output.replace(regex, value || '');
    }

    // 6. Sound / Audio tags: [sound:filename.ext]
    output = output.replace(/\[sound:([^\]]+)\]/g, (match, filename) => {
      return `
        <span class="anki-sound-container">
          <button type="button" class="anki-sound-btn" onclick="AnkiTemplateEngine.playAudio('${filename}')" title="استمع للصوت">
            🔊 <span class="sound-label">${escapeHtml(filename)}</span>
          </button>
        </span>
      `;
    });

    return output;
  };

  /**
   * Processes Cloze Deletion text containing {{cN::Answer(::Hint)?}}
   */
  const processCloze = (text, targetOrd = 1, isAnswer = false) => {
    if (!text) return '';
    const clozeRegex = /\{\{c(\d+)::([^:]+?)(?:::([^}]+?))?\}\}/g;

    return text.replace(clozeRegex, (match, numStr, answer, hint) => {
      const num = parseInt(numStr, 10);
      if (num === targetOrd) {
        if (!isAnswer) {
          const displayHint = hint ? `[${hint}]` : '[...]';
          return `<span class="cloze cloze-hidden" data-ord="${num}">${escapeHtml(displayHint)}</span>`;
        } else {
          return `<span class="cloze cloze-revealed" data-ord="${num}">${answer}</span>`;
        }
      } else {
        // Inactive cloze: show answer text normally
        return `<span class="cloze-inactive">${answer}</span>`;
      }
    });
  };

  /**
   * Injects or updates card CSS styles into document head
   */
  const applyCardCss = (cssText) => {
    let styleTag = document.getElementById('anki-dynamic-css');
    if (!styleTag) {
      styleTag = document.createElement('style');
      styleTag.id = 'anki-dynamic-css';
      document.head.appendChild(styleTag);
    }
    styleTag.textContent = cssText || '';
  };

  /**
   * Plays audio files extracted from Anki packages
   */
  const playAudio = (filename) => {
    // In Tauri, audio files are extracted to app config media directory
    // or loaded via local asset protocol / data URL
    const audio = new Audio();
    audio.src = `media/${filename}`;
    audio.play().catch(err => {
      console.warn('Could not play audio:', filename, err);
    });
  };

  const escapeRegex = (string) => {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  };

  const escapeHtml = (text) => {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  };

  return {
    render,
    processCloze,
    applyCardCss,
    playAudio
  };
})();

window.AnkiTemplateEngine = AnkiTemplateEngine;
window.playAnkiAudio = AnkiTemplateEngine.playAudio;
