export function cleanTextForTTS(text: string): string {
    if (!text) return "";

    // Remove code blocks entirely for summary/TTS
    // We assume code blocks are enclosed in ``` ... ```
    // We replace them with a brief pause marker or just space
    let clean = text.replace(/```[\s\S]*?```/g, ' ');
    
    // Also remove inline code `...` if it's just syntax? 
    // Actually, inline code is often part of the sentence: "Use `npm install` to start".
    // We probably want to keep the text inside inline code but remove the backticks.
    clean = clean.replace(/`([^`]+)`/g, '$1');

    // Remove markdown headers, bold, etc
    clean = clean
        .replace(/^[#\-*]+ /gm, '') // Remove starting bullets/headers
        .replace(/[*_]/g, '')       // Remove formatting chars (*, _)
        .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1'); // Links -> Text

    // Remove excessive whitespace
    clean = clean.replace(/\s+/g, ' ').trim();

    return clean;
}
