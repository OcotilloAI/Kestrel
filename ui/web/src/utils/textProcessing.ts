export function cleanTextForTTS(text: string): string {
    if (!text) return "";

    // Replace code blocks with a short placeholder for TTS
    // We assume code blocks are enclosed in ``` ... ```
    let clean = text.replace(/```(\w+)?\n[\s\S]*?```/g, (_, lang) => {
        const label = lang ? `${lang} code block` : 'code block';
        return ` ${label} `;
    });
    
    // Also remove inline code `...` if it's just syntax? 
    // Actually, inline code is often part of the sentence: "Use `npm install` to start".
    // We probably want to keep the text inside inline code but remove the backticks.
    clean = clean.replace(/`([^`]+)`/g, '$1');

        // Remove Goose tool headers (e.g. ─── shell | developer ───)

        // Matches lines starting with optional whitespace and 3+ dashes/box-chars

        clean = clean.replace(/^\s*[─-]{3,}.*$/gm, ' ');

        

        // Remove tool parameters (command:, path:)

        clean = clean.replace(/^\s*(command|path|file_text):.*$/gm, ' ');

        

        // Remove ls -la output (drwxr-xr-x ...)

        clean = clean.replace(/^\s*[drl-][rwx-]{9}.*$/gm, ' ');

        

        // Remove "total 28" type lines

        clean = clean.replace(/^\s*total \d+$/gm, ' ');

    

        // Remove markdown headers, bold, etc

        clean = clean

            .replace(/^\s*[#\-*]+ /gm, '') 

    // Remove excessive whitespace
    clean = clean.replace(/\s+/g, ' ').trim();

    return clean;
}

export function summarizeText(text: string): string {
    const cleaned = cleanTextForTTS(text);
    if (!cleaned) return "";

    // Split into sentences
    const sentences = cleaned.match(/[^.!?]+[.!?]+/g) || [cleaned];
    
    if (sentences.length <= 3) {
        return cleaned;
    }

    // Heuristic: First sentence + a middle sentence + last sentence
    const first = sentences[0];
    const last = sentences[sentences.length - 1];
    const middleIdx = Math.floor(sentences.length / 2);
    const middle = (middleIdx !== 0 && middleIdx !== sentences.length - 1) ? sentences[middleIdx] : "";

    return `${first} ${middle} ${last}`.replace(/\s+/g, ' ').trim();
}
