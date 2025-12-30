/**
 * Express 服务器 - 已禁用
 * 
 * 此服务器已被禁用，因为现在使用 FastAPI 后端（运行在 localhost:8000）。
 * Vite 开发服务器会将 /api 请求代理到 FastAPI 后端。
 * 
 * 如果需要运行此服务器（例如用于测试或迁移），可以执行：
 *   npm run server
 * 
 * 但请注意，此服务器提供的 API 端点应该已经迁移到 FastAPI 后端。
 * 
 * 迁移说明：
 * - /api/polish-outline -> POST /api/polish-outline (FastAPI)
 * - /api/outline -> POST /api/outline (FastAPI)
 * - /api/sources/:outlineId -> GET/POST /api/sources/:outlineId (FastAPI)
 * - /api/upload -> POST /api/upload (FastAPI)
 * - /api/generate-draft/:outlineId -> POST /api/generate-draft/:outlineId (FastAPI)
 * - /api/draft/:outlineId -> GET /api/draft/:outlineId (FastAPI)
 */

// 注意：此服务器已被禁用，现在使用 FastAPI 后端
// 如果需要启用此服务器进行测试，请取消注释 app.listen() 部分

import express from 'express';
import cors from 'cors';
import bodyParser from 'body-parser';
import multer from 'multer';
import path from 'path';
import { fileURLToPath } from 'url';
import OpenAI from 'openai';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = 3001;

// 注意：服务器启动代码在文件末尾已被注释，默认不启动

// Make OpenAI optional - only initialize if API key is provided
let openai = null;
if (process.env.OPENAI_API_KEY) {
  openai = new OpenAI({
    apiKey: process.env.OPENAI_API_KEY,
    baseURL: 'https://api.chatanywhere.org/v1'
  });
}

app.use(cors());
app.use(bodyParser.json());
app.use('/uploads', express.static(path.join(__dirname, 'uploads')));
// Serve Energy Storage Chinese PDFs
app.use('/pdfs', express.static(path.join(__dirname, '..', 'Energy Storage Chinese')));

const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    cb(null, 'server/uploads/');
  },
  filename: (req, file, cb) => {
    cb(null, Date.now() + '-' + file.originalname);
  }
});

const upload = multer({ 
  storage,
  limits: { fileSize: 50 * 1024 * 1024 }
});

let outlines = {};
let sources = {};
let drafts = {};

const mockSources = [
  {
    id: 1,
    title: 'Selected technologies of electrochemical energy storage—a review',
    authors: 'K Detka, K Górecki',
    year: '2023',
    domain: 'mdpi.com',
    cited: 48,
    recommended: true,
    excerpt: 'of the considered electrochemical energy storage devices and ... The classification of energy storage technologies most often ... storage devices used in electric vehicles of various brands. ...'
  },
  {
    id: 2,
    title: 'Chemical energy storage',
    authors: 'ST Revankar',
    year: '2019',
    domain: 'Elsevier',
    cited: 144,
    recommended: true,
    excerpt: 'Various type of batteries to store electric energy are described from lead-acid batteries, to ... The electrochemical capacitors are then described. For each storage devices, chemistry, ...'
  },
  {
    id: 3,
    title: 'Encyclopedia of electrochemical power sources',
    authors: 'J Garche',
    year: '2024',
    domain: 'books.google.com',
    cited: 1042,
    recommended: true,
    excerpt: 'technology for storing electricity is electrochemical energy sources, which store electricity in the form of chemical ... and function of the various types of power sources, as ...'
  },
  {
    id: 4,
    title: 'Electrochemical methods: fundamentals and applications',
    authors: 'AJ Bard, LR Faulkner, HS White',
    year: '2001',
    domain: 'Wiley',
    cited: 63847,
    recommended: true,
    excerpt: 'It is a self-contained volume, developing all key ideas ... students taking courses in electrochemistry, physical and ... electrochemistry and electrochemical engineering, energy storage ...'
  },
  {
    id: 5,
    title: 'An updated review of energy storage systems: Classification and applications in distributed generation power systems',
    authors: 'O Krishan, S Suhag',
    year: '2019',
    domain: 'Wiley',
    cited: 338,
    recommended: false,
    excerpt: 'Energy storage systems (ESSs) are becoming essential in power systems, particularly with the proliferation of renewable energy sources. This paper provides an updated review of ESSs, focusing on their classification and applications in distributed generation power systems.'
  }
];

app.post('/api/polish-outline', async (req, res) => {
  const { outlineText } = req.body;
  
  if (!outlineText || !outlineText.trim()) {
    return res.status(400).json({ success: false, error: '大纲内容不能为空' });
  }

  if (!openai) {
    return res.status(503).json({ success: false, error: 'AI服务未配置，请设置OPENAI_API_KEY环境变量' });
  }

  try {
    const completion = await openai.chat.completions.create({
      model: 'gpt-4',
      messages: [
        {
          role: 'system',
          content: `You are a senior energy policy analysis expert. 
Your task is to review and optimize a Chinese user's White Paper draft outline. The user writes in Chinese, and you must also reply in **Chinese**.  

Refine the outline by:
- Clarifying structure and logic
- Expanding incomplete sections
- Adding key analytical points, data needs, and potential case studies
- Ensuring the outline is ready for professional white paper generation  

Your output should include:
- Improved chapter titles and brief explanations  
- Key analysis points or questions  
- Recommended data sources or reference types  
- A short summary of improvement suggestions  

Keep your tone formal, analytical, and suitable for government or industry white papers.`
        },
        {
          role: 'user',
          content: outlineText
        }
      ],
      temperature: 0.7,
      max_tokens: 2000
    });

    const polishedOutline = completion.choices[0].message.content;

    res.json({
      success: true,
      polishedOutline
    });
  } catch (error) {
    console.error('OpenAI API error:', error);
    res.status(500).json({ 
      success: false, 
      error: 'AI优化失败，请稍后重试',
      details: error.message 
    });
  }
});

app.post('/api/outline', (req, res) => {
  const { outlineText, config } = req.body;
  const id = Date.now().toString();
  
  outlines[id] = {
    id,
    text: outlineText,
    config,
    createdAt: new Date().toISOString()
  };
  
  res.json({ 
    success: true, 
    outlineId: id,
    optimizedOutline: outlineText
  });
});

app.get('/api/sources/:outlineId', (req, res) => {
  res.json({
    success: true,
    sources: mockSources
  });
});

app.post('/api/sources/:outlineId', (req, res) => {
  const { outlineId } = req.params;
  const { selectedSources, customUrls } = req.body;
  
  sources[outlineId] = {
    selected: selectedSources,
    custom: customUrls || []
  };
  
  res.json({ success: true });
});

app.post('/api/upload', upload.single('file'), (req, res) => {
  if (!req.file) {
    return res.status(400).json({ success: false, error: 'No file uploaded' });
  }
  
  res.json({
    success: true,
    file: {
      filename: req.file.originalname,
      path: req.file.path,
      size: req.file.size
    }
  });
});

app.post('/api/generate-draft/:outlineId', (req, res) => {
  const { outlineId } = req.params;
  const outline = outlines[outlineId];
  const selectedSources = sources[outlineId];
  
  const mockDraft = `# 未来五年储能产业政策与发展趋势白皮书

## 前言

在"双碳"战略目标与新型电力系统加速构建的时代背景下，储能产业正成为全球能源转型的重要支撑力量。过去五年间，电化学储能技术快速迭代，产业链成本持续下降，政策体系逐步完善，储能从"示范阶段"迈向"市场化应用阶段"。然而，面对能源安全、技术自主化、市场规则尚不完善等挑战，未来五年的政策方向与发展路径亟需系统性梳理与战略规划。

本白皮书基于国际能源署（IEA）、彭博新能源财经（BNEF）、中国能源研究会储能专委会等机构的公开资料，结合对国内外政策文本、市场数据与技术趋势的分析，旨在：
1. 总结储能政策演进与市场格局；
2. 提炼全球储能发展的关键规律与政策启示；
3. 展望未来五年政策走向与产业升级路径；
4. 为政府决策、企业布局及资本投资提供数据支撑与政策建议

白皮书内容结构如下：第一章分析储能产业的战略定位与发展背景；第二章聚焦全球储能政策与市场格局；第三章将回顾我国储能政策体系演变；后续章节将分别探讨技术趋势、商业模式、监管机制与未来路径图。

---

## 第一章 战略定位与发展背景

### 1.1 储能在能源转型中的核心角色

储能是实现能源系统灵活性与安全性的关键环节。根据《Global Energy Storage Policy Landscape 2024》（IEA, 2024）报告，储能系统不仅支撑可再生能源高比例接入，还在电力调频、峰谷调节、应急保障等方面发挥战略作用。储能的发展水平已成为衡量一个国家能源转型能力与能源安全韧性的核心指标。

在我国，"十四五"以来储能被正式纳入国家能源战略布局。国家能源局于2024年发布的《储能发展路线图（2025–2030）》提出，到2030年新型储能装机规模将超过1亿千瓦时，形成"安全可控、市场驱动、技术多元"的新格局。

### 1.2 政策驱动与市场演化阶段

过去五年，中国储能产业经历了从政策引导到市场驱动的转变：
- **2017–2019年**：政策示范期，以项目试点与技术验证为主；
- **2020–2022年**：市场启动期，形成"新能源+储能"并网机制；
- **2023–2025年**：市场深化期，储能被纳入电力辅助服务与容量市场。

国际上，美国通过《Inflation Reduction Act》引入储能投资税收抵免（ITC）；欧盟强化储能在能源市场中的独立主体地位；日本和韩国则重点推动家庭与工商业分布式储能。全球政策趋势表明，政策激励正在从"补贴导向"转向"市场机制导向"。

### 1.3 产业结构与创新热点

当前储能产业链主要由四个环节构成：材料制造、电池系统集成、运营调度与回收利用。根据 BloombergNEF (2024) 数据，全球电化学储能系统成本自2015年以来下降超过70%，固态电池与钠离子电池成为中长期技术突破的重点方向。与此同时，数字孪生、AI预测调度与虚拟电厂（VPP）技术的融合正重塑储能系统的运行模式。

### 1.4 战略意义与政策启示

储能不仅是支撑能源转型的关键基础设施，更是未来能源体系智能化的重要引擎。未来政策应在以下方面发力：
1. 构建储能容量市场与辅助服务定价机制；
2. 建立统一的储能安全与性能标准体系；
3. 推动核心材料与设备本土化制造；
4. 鼓励"储能+可再生能源""储能+交通""储能+建筑"融合应用。

---

## 第二章 全球储能政策与市场格局

### 2.1 全球储能产业总体态势

截至2024年底，全球累计储能装机容量超过230GW/500GWh，同比增长46%。欧美地区继续引领市场总量，而中国、印度、澳大利亚则成为增长最快的区域市场。根据 Global Energy Storage Market Outlook 2025 (BNEF, 2024)，全球储能投资预计将在2025年突破1000亿美元，其中电化学储能占比超85%。

### 2.2 各主要经济体政策框架比较

不同国家的储能政策呈现明显差异化特征：

**美国**：以投资税收抵免（ITC）为核心，支持储能独立参与电力市场，鼓励"储能+可再生能源"项目捆绑开发。加州、德州等州推动储能强制配置政策。

**欧盟**：将储能定位为独立市场主体，允许参与容量市场与辅助服务市场。德国、英国通过虚拟电厂（VPP）模式推动分布式储能聚合交易。

**中国**：从"示范项目"走向"市场化机制"，通过电价峰谷差、辅助服务补偿机制、容量电价等方式引导储能投资。政策重点从规模扩张转向质量提升与标准规范。

**日本与韩国**：聚焦家庭与工商业储能应用，通过补贴与低息贷款支持分布式储能部署，强调储能在能源安全与应急保障中的作用。

---

（续...）`;

  drafts[outlineId] = {
    content: mockDraft,
    sources: selectedSources,
    generatedAt: new Date().toISOString()
  };
  
  res.json({
    success: true,
    draft: mockDraft
  });
});

app.get('/api/draft/:outlineId', (req, res) => {
  const { outlineId } = req.params;
  const draft = drafts[outlineId];
  
  if (!draft) {
    return res.status(404).json({ success: false, error: 'Draft not found' });
  }
  
  res.json({
    success: true,
    draft: draft.content,
    sources: sources[outlineId]
  });
});

app.post('/api/chat', (req, res) => {
  const { message, outlineId } = req.body;
  
  const mockResponses = [
    '根据已选择的资料，储能技术主要分为电化学储能、电气储能、机械储能和化学储能四大类。其中电化学储能（电池）是目前应用最广泛的技术。',
    '锂离子电池因其高能量密度、长循环寿命和较低的自放电率，成为当前最主流的储能技术之一，广泛应用于电动汽车和电网储能系统中。',
    '根据知识库数据，全球储能市场预计在2025年达到约500亿美元的规模，年均复合增长率超过20%。',
    '储能系统的关键性能指标包括：能量密度、功率密度、循环寿命、库仑效率和单位千瓦时成本。这些指标直接影响储能系统的应用场景和经济性。'
  ];
  
  const response = mockResponses[Math.floor(Math.random() * mockResponses.length)];
  
  res.json({
    success: true,
    response,
    timestamp: new Date().toISOString()
  });
});

app.post('/api/analyze-whitepaper', async (req, res) => {
  const { content } = req.body;
  
  if (!content || !content.trim()) {
    return res.status(400).json({ success: false, error: '白皮书内容不能为空' });
  }

  if (!openai) {
    return res.status(503).json({ success: false, error: 'AI服务未配置，请设置OPENAI_API_KEY环境变量' });
  }

  try {
    const completion = await openai.chat.completions.create({
      model: 'gpt-4',
      messages: [
        {
          role: 'system',
          content: `You are a senior white paper quality analyst and editor specializing in energy policy and industry analysis. 
Analyze the provided white paper content and give detailed feedback in **Chinese**. Your analysis should cover:

1. **内容质量评估**（Content Quality）
   - 论述深度与全面性
   - 数据支撑与证据充分性
   - 逻辑严密性与论证结构

2. **结构分析**（Structure Analysis）
   - 章节安排是否合理
   - 前后逻辑连贯性
   - 重点突出程度

3. **专业性与可信度**（Credibility）
   - 术语使用准确性
   - 引用文献质量
   - 行业洞察深度

4. **改进建议**（Improvement Recommendations）
   - 需要补充的内容或数据
   - 可以删减或简化的部分
   - 表达方式优化建议
   - 可视化建议（图表、数据表等）

5. **总体评分**（Overall Rating）
   - 给出1-10分的综合评分
   - 简要总结优点和待改进点

Your tone should be constructive, professional, and actionable.`
        },
        {
          role: 'user',
          content: `请分析以下白皮书内容：\n\n${content}`
        }
      ],
      temperature: 0.7,
      max_tokens: 2000
    });

    const analysis = completion.choices[0]?.message?.content;
    
    res.json({
      success: true,
      analysis,
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    console.error('Error analyzing whitepaper:', error);
    res.status(500).json({ 
      success: false, 
      error: 'AI分析失败，请稍后重试',
      details: error.message 
    });
  }
});

app.get('/api/history', (req, res) => {
  const history = Object.values(outlines).map(outline => ({
    id: outline.id,
    title: outline.config?.docType || '政策分析报告',
    date: new Date(outline.createdAt).toLocaleDateString('zh-CN'),
    hasDraft: !!drafts[outline.id]
  }));
  
  res.json({
    success: true,
    history
  });
});

// 服务器启动代码已禁用 - 现在使用 FastAPI 后端
// 如果需要启用此服务器，请取消注释以下代码
/*
app.listen(PORT, 'localhost', () => {
  console.log(`Backend server running on http://localhost:${PORT}`);
});
*/
