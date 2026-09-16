const PORT = process.env.PORT ?? 3000;

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization",
};

function createSSEResponse(min: number, max: number, intervalMs: number = 1000, roverId: number = 100) {
  let timer: ReturnType<typeof setInterval>;
  const textEncoder = new TextEncoder() ;

  const stream = new ReadableStream({
    start(controller) {
      timer = setInterval(() => {
        const randomValue = (Math.random() * (max - min) + min).toFixed(2);
        const data = JSON.stringify({ data: parseFloat(randomValue), rover_id: roverId });
        controller.enqueue(textEncoder.encode(`data: ${data}\n\n`));
      }, intervalMs);
    },
    cancel() {
      clearInterval(timer);
    }
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      "Connection": "keep-alive",
      ...corsHeaders
    }
  });
}

const server = Bun.serve({
  port: PORT,
  fetch(req) {
    // Handle CORS preflight requests
    if (req.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders });
    }

    const url = new URL(req.url);

    if (url.pathname === "/") {
      return new Response("working perfectly fine ", { headers: corsHeaders });
    }

    if (url.pathname === "/temp" || url.pathname === "/humd" || url.pathname === "/dist") {
      return createSSEResponse(50, 100, 1000, 100);
    }

    if (url.pathname === "/video") {
      return new Response("", { headers: corsHeaders });
    }

    return new Response("Not Found", { status: 404, headers: corsHeaders });
  }
});

console.log(`running on ${server.hostname}:${server.port}`);
