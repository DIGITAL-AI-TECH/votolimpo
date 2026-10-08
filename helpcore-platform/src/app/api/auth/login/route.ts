import { NextRequest, NextResponse } from "next/server";
import { timingSafeEqual } from "crypto";
import { setSessionCookie } from "@/lib/auth";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { password } = body;

    if (!password || typeof password !== "string") {
      return NextResponse.json(
        { error: "Senha obrigatória" },
        { status: 400 }
      );
    }

    const correctPassword = process.env.HELPCORE_AUTH_PASSWORD;
    if (!correctPassword) {
      console.error("HELPCORE_AUTH_PASSWORD not set");
      return NextResponse.json(
        { error: "Erro interno de configuração" },
        { status: 500 }
      );
    }

    const pwBuf = Buffer.from(password);
    const correctBuf = Buffer.from(correctPassword);
    if (pwBuf.length !== correctBuf.length || !timingSafeEqual(pwBuf, correctBuf)) {
      return NextResponse.json(
        { error: "Senha incorreta" },
        { status: 401 }
      );
    }

    await setSessionCookie();
    return NextResponse.json({ ok: true });
  } catch {
    return NextResponse.json(
      { error: "Erro interno" },
      { status: 500 }
    );
  }
}
