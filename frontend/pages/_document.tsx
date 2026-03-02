import { Html, Head, Main, NextScript } from 'next/document';

export default function Document() {
  return (
    <Html lang="ko">
      <Head>
        <link rel="icon" href="/favicon.ico" sizes="32x32" />
        <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
        <link
          href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;600;700&family=Noto+Serif+KR:wght@400;700&display=swap"
          rel="stylesheet"
        />
        <meta name="description" content="장기 챔피언 AI - 웹 기반 인간 대 AI 장기 게임" />
      </Head>
      <body>
        <Main />
        <NextScript />
      </body>
    </Html>
  );
}
