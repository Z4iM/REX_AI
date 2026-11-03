import { init } from "@heyputer/puter.js/src/init.cjs";

let stage = "configuration";
try {
    let prompt = "";
    for await (const chunk of process.stdin.setEncoding("utf8")) {
        prompt += chunk;
        if (prompt.length > 5000) throw new Error("Prompt too long");
    }
    const token = process.env.PUTER_AUTH_TOKEN;
    if (!token || !prompt.trim()) throw new Error("Missing configuration");
    stage = "provider";
    const client = init(token);
    client.config = { ...client.config, autoRetry: false };
    const image = await client.ai.txt2img(prompt, {
        model: "openai/gpt-image-2.5-flare",
        quality: "low",
        size: "1536x1024",
    });
    stage = "image-response";
    const src = image?.src;
    // Consume only inline image data. Never fetch an arbitrary returned URL.
    const prefix = /^data:image\/(?:png|jpeg|webp);base64,/i.exec(src || "");
    if (!prefix || src.length > 14_000_000) throw new Error("Unexpected image response");
    process.stdout.write(Buffer.from(src.slice(prefix[0].length), "base64"), () => process.exit(0));
} catch (error) {
    const status = Number(error?.status ?? error?.statusCode ?? error?.response?.status);
    const statusLabel = Number.isInteger(status) && status >= 400 && status <= 599 ? ` HTTP ${status}` : "";
    const knownCodes = new Set(["unauthorized", "invalid_token", "insufficient_funds", "insufficient_credits",
        "rate_limit_exceeded", "invalid_image_response", "permission_denied"]);
    const code = knownCodes.has(error?.code) ? ` ${error.code}` : "";
    process.stderr.write(`Puter cover failed at ${stage}${statusLabel}${code}.\n`, () => process.exit(1));
}
