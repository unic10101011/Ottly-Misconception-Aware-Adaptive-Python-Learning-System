import React from 'react'

const difficultyLabels = { 1: '基础', 2: '巩固', 3: '综合' }

export default function ProblemMetadata({ version, difficulty, knowledgeIds = [], knowledgeNames = {} }) {
  return <p className="problem-metadata">
    {version == null ? '历史版本未提供' : `版本 ${version}`} · 难度：{difficultyLabels[difficulty] || '历史记录未提供'}
    {' · 知识点：'}{knowledgeIds.length ? knowledgeIds.map(id => knowledgeNames[id] || id).join('、') : '历史记录未提供'}
  </p>
}
