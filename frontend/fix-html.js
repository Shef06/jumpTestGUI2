// Script per modificare index.html per supportare file://
// - Rimuove type="module"
// - Rinomina i file in bundle.js e bundle.css
// - Assicura percorsi relativi
import { readFileSync, writeFileSync } from 'fs';
import { join } from 'path';
import { readdirSync } from 'fs';

const distPath = join(process.cwd(), 'dist', 'index.html');
const distDir = join(process.cwd(), 'dist');

try {
  let html = readFileSync(distPath, 'utf-8');
  
  // Trova i file generati
  const files = readdirSync(distDir);
  const jsFile = files.find(f => f.endsWith('.js') && f.startsWith('index-') || f === 'bundle.js');
  const cssFile = files.find(f => f.endsWith('.css') && (f.includes('style') || f.includes('app') || f === 'bundle.css'));
  
  // Sostituisci i riferimenti ai file generati con bundle.js e bundle.css
  if (jsFile && jsFile !== 'bundle.js') {
    // Rinomina il file JS
    const oldJsPath = join(distDir, jsFile);
    const newJsPath = join(distDir, 'bundle.js');
    try {
      const jsContent = readFileSync(oldJsPath);
      writeFileSync(newJsPath, jsContent);
      // Rimuovi il vecchio file
      try {
        const { unlinkSync } = require('fs');
        unlinkSync(oldJsPath);
      } catch {}
    } catch (e) {
      console.warn('⚠️  Impossibile rinominare il file JS:', e.message);
    }
  }
  
  if (cssFile && cssFile !== 'bundle.css') {
    // Rinomina il file CSS
    const oldCssPath = join(distDir, cssFile);
    const newCssPath = join(distDir, 'bundle.css');
    try {
      const cssContent = readFileSync(oldCssPath);
      writeFileSync(newCssPath, cssContent);
      // Rimuovi il vecchio file
      try {
        const { unlinkSync } = require('fs');
        unlinkSync(oldCssPath);
      } catch {}
    } catch (e) {
      console.warn('⚠️  Impossibile rinominare il file CSS:', e.message);
    }
  }
  
  // Trova e rimuovi gli script esistenti dal head
  html = html.replace(/<script[^>]*src="[^"]*index-[^"]*\.js"[^>]*>.*?<\/script>/g, '');
  html = html.replace(/<script[^>]*src="[^"]*assets\/[^"]*\.js"[^>]*>.*?<\/script>/g, '');
  html = html.replace(/<script[^>]*src="[^"]*bundle\.js"[^>]*>.*?<\/script>/g, '');
  
  // Trova e rimuovi i link CSS esistenti
  html = html.replace(/<link[^>]*href="[^"]*style[^"]*\.css"[^>]*>/g, '');
  html = html.replace(/<link[^>]*href="[^"]*app[^"]*\.css"[^>]*>/g, '');
  html = html.replace(/<link[^>]*href="[^"]*assets\/[^"]*\.css"[^>]*>/g, '');
  html = html.replace(/<link[^>]*href="[^"]*bundle\.css"[^>]*>/g, '');
  
  // Rimuovi type="module" e crossorigin dagli script rimanenti
  html = html.replace(/type="module"/g, '');
  html = html.replace(/\s+crossorigin/g, '');
  html = html.replace(/crossorigin\s*/g, '');
  
  // Assicura percorsi relativi
  html = html.replace(/src="\//g, 'src="./');
  html = html.replace(/href="\//g, 'href="./');
  
  // Aggiungi CSS nel head (prima di </head>)
  html = html.replace(/<\/head>/, '    <link rel="stylesheet" href="./bundle.css">\n  </head>');
  
  // Aggiungi JS alla fine del body (prima di </body>, dopo #app)
  html = html.replace(/<\/body>/, '    <!-- Script alla fine del body per assicurare che #app esista -->\n    <script src="./bundle.js"></script>\n  </body>');
  
  writeFileSync(distPath, html, 'utf-8');
  console.log('✅ HTML modificato per supportare file://');
  console.log('✅ File rinominati in bundle.js e bundle.css');
} catch (error) {
  console.error('❌ Errore durante la modifica dell\'HTML:', error);
  process.exit(1);
}

