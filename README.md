<div align="center">

<!-- logo -->

![header](https://capsule-render.vercel.app/api?type=Waving&color=auto&height=200&section=header&text=무장애여행)

🤖LLM 기반 Agent Project



<img  src="https://camo.githubusercontent.com/3611f930d3bdf0674c4f407d7c56870354310bf3dbc057a088a224a9a6841b67/68747470733a2f2f696d672e736869656c64732e696f2f62616467652f53747265616d6c69742d312e33352d4646344234423f7374796c653d666c61742d737175617265266c6f676f3d73747265616d6c6974266c6f676f436f6c6f723d7768697465" />
<img  src=
"https://camo.githubusercontent.com/a4598a7970ccfa3ddfd1cdddb36487c83152a9e4a53f0dd7f66654d4ba785821/68747470733a2f2f696d672e736869656c64732e696f2f62616467652f507974686f6e2d332e31312b2d3337373641423f7374796c653d666c61742d737175617265266c6f676f3d707974686f6e266c6f676f436f6c6f723d7768697465" />
<img src = "https://camo.githubusercontent.com/79847b6121e3835e55f6d9db0af1c456169848101dcd69a539405757f5f3650d/68747470733a2f2f696d672e736869656c64732e696f2f62616467652f4f70656e41492d4750542d2d342d3431323939313f7374796c653d666c61742d737175617265266c6f676f3d6f70656e6169266c6f676f436f6c6f723d7768697465">
<img src ="https://camo.githubusercontent.com/a76db881b82241c7d00437b7949733cbd46e5a6720ab9e637b0fee2d190f1040/68747470733a2f2f696d672e736869656c64732e696f2f62616467652f446f636b65722d436f6d706f73652d3234393645443f7374796c653d666c61742d737175617265266c6f676f3d646f636b6572266c6f676f436f6c6f723d7768697465">
<br/> <img src="https://img.shields.io/badge/프로젝트 기간-2026.04.15~2026.04.28-green?style=flat&logo=&logoColor=white" />

</div>

<br />

## 📑 목차

- [📝 서비스 목적 및 문제 정의](#-서비스-목적-및-문제-정의)
- [🗂️ 해결 방향](#-해결-방향)
- [🖥️ 화면 구성](#️-화면-구성)
- [🗂️ APIs](#️-apis)
- [🤔 배포](#-배포)
- [⚙ 기술 스택](#-기술-스택)
- [🛠️ 프로젝트 아키텍쳐](#️-프로젝트-아키텍쳐)
- [🔧 기술적 이슈와 해결 과정](#-기술적-이슈와-해결-과정)

<br />

## 📝 서비스-목적-및-문제-정의

**배경**
국내 교통약자(휠체어 이용자, 노인, 영유아 동반 가족 등)는 여행 계획 시 접근성 정보를 얻기 위해 수십 개의 공공 데이터 포털, 관광지 공식 홈페이지, 블로그 후기를 직접 확인해야 한다. 한국관광공사 API는 관광지 기본 정보를 제공하지만 접근성 필드는 대부분 비어 있거나 부정확하다.

**핵심 문제**

| 문제 | 설명 |
| :-: | :-: |
| 정보 분산 | 접근성 정보가 공공 API, 블로그, SNS, 지자체 홈페이지 등에 분산 |
| 최신성 부족 | 공공 데이터의 접근성 항목은 수년간 갱신되지 않는 경우 다수 |
| 개인화 부족 | 휠체어 사용자, 시각장애인, 유모차 동반 등 요구사항이 다름에도 일괄 제공 |
| 일정 통합 불가 | 접근성 정보와 여행 일정 생성이 분리되어 수동 조합 필요 |
| 신뢰성 검증 불가 | 제공된 정보가 실제 방문 시 맞는지 사전 확인 수단 없음 |

**목표**
교통약자가 자연어로 여행 조건을 입력하면 → 접근성 검증이 완료된 장소만으로 구성된 맞춤 일정을 자동 생성하는 AI 시스템 구축

<br />

## 🖥️ 해결 방향

<br />

## 🖥️ 화면 구성

| Screen #1 | Screen #2 |
| :---: | :---: |
| <img src="https://www.image2url.com/r2/default/images/1777358145266-8182989c-a9a6-4798-be8c-825796d2d31e.png" width="400"/> | <img src="https://www.image2url.com/r2/default/images/1777358494181-8c344287-f775-439f-acb4-1a74bbc03f4c.png" width="400"/> |

**프로토타입**

<img src="https://i.postimg.cc/nrTzGhKC/llmhwamyeon1.png">

<br />

## 🗂️ APIs

작성한 API는 아래에서 확인할 수 있습니다.

👉🏻 [API 바로보기](/backend/APIs.md)

<br />

## 🤔 배포

Ngrok, Streamlit Cloud 배포

<br />

## ⚙ 기술 스택

> skills 폴더에 있는 아이콘을 이용할 수 있습니다.

### Back-end
<div>
<img src="https://github.com/yewon-Noh/readme-template/blob/main/skills/Java.png?raw=true" width="80">
<img src="https://github.com/yewon-Noh/readme-template/blob/main/skills/SpringBoot.png?raw=true" width="80">
<img src="https://github.com/yewon-Noh/readme-template/blob/main/skills/SpringSecurity.png?raw=true" width="80">
<img src="https://github.com/yewon-Noh/readme-template/blob/main/skills/SpringDataJPA.png?raw=true" width="80">
<img src="https://github.com/yewon-Noh/readme-template/blob/main/skills/Mysql.png?raw=true" width="80">
<img src="https://github.com/yewon-Noh/readme-template/blob/main/skills/Ajax.png?raw=true" width="80">
<img src="https://github.com/yewon-Noh/readme-template/blob/main/skills/Thymeleaf.png?raw=true" width="80">
</div>

### Infra
<div>
<img src="https://github.com/yewon-Noh/readme-template/blob/main/skills/AWSEC2.png?raw=true" width="80">
</div>

### Tools
<div>
<img src="https://github.com/yewon-Noh/readme-template/blob/main/skills/Github.png?raw=true" width="80">
<img src="https://github.com/yewon-Noh/readme-template/blob/main/skills/Notion.png?raw=true" width="80">
</div>

<br />

## 🛠️ 프로젝트 아키텍쳐

![no-image](https://user-images.githubusercontent.com/80824750/208294567-738dd273-e137-4bbf-8307-aff64258fe03.png)

<br />

## 🔧 기술적 이슈와 해결 과정

- Stream 써야할까?
    - [Stream API에 대하여](https://velog.io/@yewo2nn16/Java-Stream-API)
- Gmail STMP 이용하여 이메일 전송하기
    - [gmail 보내기](https://velog.io/@yewo2nn16/Email-이메일-전송하기with-첨부파일)
- AWS EC2에 배포하기
    - [서버 배포하기-1](https://velog.io/@yewo2nn16/SpringBoot-서버-배포)
    - [서버 배포하기-2](https://velog.io/@yewo2nn16/SpringBoot-서버-배포-인텔리제이에서-jar-파일-빌드해서-배포하기)
