import {
  useGetChunkHighlights,
  useGetDocumentUrl,
} from '@/hooks/document-hooks';
import { IReferenceChunk } from '@/interfaces/database/chat';
import { IChunk } from '@/interfaces/database/knowledge';
import FileError from '@/pages/document-viewer/file-error';
import Excel from '@/pages/document-viewer/excel';
import Docx from '@/pages/document-viewer/docx';
import { Skeleton, Flex, Spin } from 'antd';
import { useEffect, useRef, useState } from 'react';
import {
  AreaHighlight,
  Highlight,
  IHighlight,
  PdfHighlighter,
  PdfLoader,
  Popup,
} from 'react-pdf-highlighter';
import { useCatchDocumentError } from './hooks';
import { Authorization } from '@/constants/authorization';
import { getAuthorization } from '@/utils/authorization-util';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import styles from './index.less';

interface IProps {
  chunk: IChunk | IReferenceChunk;
  documentId: string;
  visible: boolean;
}

const HighlightPopup = ({
  comment,
}: {
  comment: { text: string; emoji: string };
}) =>
  comment.text ? (
    <div className="Highlight__popup">
      {comment.emoji} {comment.text}
    </div>
  ) : null;

const DocumentPreviewer = ({ chunk, documentId, visible }: IProps) => {
  const getDocumentUrl = useGetDocumentUrl(documentId);
  const { highlights: state, setWidthAndHeight } = useGetChunkHighlights(chunk);
  const ref = useRef<(highlight: IHighlight) => void>(() => {});
  const [loaded, setLoaded] = useState(false);
  const url = getDocumentUrl();
  const error = useCatchDocumentError(url);

  // 添加文本文件处理状态（txt, md等）
  const [textContent, setTextContent] = useState<string>('');
  const [textLoading, setTextLoading] = useState(false);
  const [textError, setTextError] = useState<string>('');

  // 检测文件类型
  const getFileExtension = (chunk: IChunk | IReferenceChunk) => {
    if ('docnm_kwd' in chunk) {
      // IReferenceChunk 类型
      const fileName = chunk.docnm_kwd || '';
      if (typeof fileName === 'string') {
        const ext = fileName.split('.').pop()?.toLowerCase();
        return ext;
      }
    }
    // 其他情况，暂时返回pdf作为默认值
    return 'pdf';
  };

  const fileExtension = getFileExtension(chunk);

  // 添加调试信息（仅在开发环境）
  useEffect(() => {
    if (process.env.NODE_ENV === 'development') {
      console.log('DocumentPreviewer mounted with:', {
        documentId,
        fileExtension,
        url,
        chunk
      });
    }
  }, []);

  const resetHash = () => {};

  useEffect(() => {
    setLoaded(visible);
  }, [visible]);

  useEffect(() => {
    if (state.length > 0 && loaded) {
      setLoaded(false);
      ref.current(state[0]);
    }
  }, [state, loaded]);

  // 处理文本文件的useEffect（txt, md等）
  useEffect(() => {
    if (['txt', 'md'].includes(fileExtension || '') && url && visible) {
      const fetchTextContent = async () => {
        try {
          if (process.env.NODE_ENV === 'development') {
            console.log('Starting to fetch txt content from:', url);
          }
          setTextLoading(true);
          setTextError('');

          const response = await fetch(url, {
            headers: {
              [Authorization]: getAuthorization(),
            },
          });

          if (process.env.NODE_ENV === 'development') {
            console.log('Response received:', response.status, response.statusText);
          }

          if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
          }

          const text = await response.text();
          if (process.env.NODE_ENV === 'development') {
            console.log('Text content loaded successfully, length:', text.length);
          }
          setTextContent(text);
        } catch (err: any) {
          console.error('Failed to load text file:', err);
          setTextError(err.message || 'Failed to load text file');
        } finally {
          setTextLoading(false);
        }
      };

      fetchTextContent();
    }
  }, [url, fileExtension, visible]);

  // 根据文件类型渲染不同的预览组件
  if (fileExtension === 'txt') {
  return (
    <div className={styles.documentContainer}>
        {textLoading && (
          <Flex justify="center" align="center" style={{ height: '200px' }}>
            <Spin size="large" />
          </Flex>
        )}
        {textError && <FileError>{textError}</FileError>}
        {!textLoading && !textError && textContent && (
          <pre style={{
            width: '100%',
            maxWidth: '100%',
            height: 'auto',
            padding: '16px',
            margin: 0,
            backgroundColor: '#fafafa',
            border: '1px solid #d9d9d9',
            borderRadius: '6px',
            fontFamily: "'Monaco', 'Menlo', 'Ubuntu Mono', monospace",
            fontSize: '14px',
            lineHeight: '1.6',
            color: '#262626',
            whiteSpace: 'pre-wrap',
            wordWrap: 'break-word',
            overflowWrap: 'break-word',
            overflow: 'auto',
            maxHeight: '100%'
          }}>
            {textContent}
          </pre>
        )}
        {!textLoading && !textError && !textContent && (
          <FileError>文件内容为空</FileError>
        )}
      </div>
    );
  }

  // Markdown文件预览
  if (fileExtension === 'md') {
    return (
      <div className={styles.documentContainer}>
        {textLoading && (
          <Flex justify="center" align="center" style={{ height: '200px' }}>
            <Spin size="large" />
          </Flex>
        )}
        {textError && <FileError>{textError}</FileError>}
        {!textLoading && !textError && textContent && (
          <div style={{
            width: '100%',
            maxWidth: '100%',
            height: 'auto',
            padding: '16px',
            margin: 0,
            backgroundColor: '#ffffff',
            border: '1px solid #d9d9d9',
            borderRadius: '6px',
            overflow: 'auto',
            maxHeight: '100%'
          }}>
                        <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                // 自定义样式组件
                h1: ({node, ...props}) => <h1 style={{color: '#262626', fontSize: '24px', marginBottom: '16px', fontWeight: 'bold'}} {...props} />,
                h2: ({node, ...props}) => <h2 style={{color: '#262626', fontSize: '20px', marginBottom: '14px', fontWeight: 'bold'}} {...props} />,
                h3: ({node, ...props}) => <h3 style={{color: '#262626', fontSize: '18px', marginBottom: '12px', fontWeight: 'bold'}} {...props} />,
                h4: ({node, ...props}) => <h4 style={{color: '#262626', fontSize: '16px', marginBottom: '10px', fontWeight: 'bold'}} {...props} />,
                h5: ({node, ...props}) => <h5 style={{color: '#262626', fontSize: '14px', marginBottom: '8px', fontWeight: 'bold'}} {...props} />,
                h6: ({node, ...props}) => <h6 style={{color: '#262626', fontSize: '12px', marginBottom: '6px', fontWeight: 'bold'}} {...props} />,
                p: ({node, ...props}) => <p style={{color: '#262626', lineHeight: '1.6', marginBottom: '12px'}} {...props} />,
                code: ({node, ...props}) => {
                  const isInline = !props.className?.includes('language-');
                  return isInline ? 
                    <code style={{backgroundColor: '#f5f5f5', padding: '2px 4px', borderRadius: '4px', fontFamily: 'Monaco, Consolas, monospace', fontSize: '13px', color: '#e53e3e'}} {...props} /> :
                    <code style={{backgroundColor: '#f5f5f5', padding: '12px', borderRadius: '6px', display: 'block', fontFamily: 'Monaco, Consolas, monospace', fontSize: '13px', overflow: 'auto', lineHeight: '1.5'}} {...props} />;
                },
                pre: ({node, ...props}) => <pre style={{backgroundColor: '#f5f5f5', padding: '12px', borderRadius: '6px', overflow: 'auto', marginBottom: '16px'}} {...props} />,
                blockquote: ({node, ...props}) => <blockquote style={{borderLeft: '4px solid #d9d9d9', paddingLeft: '16px', margin: '16px 0', fontStyle: 'italic', color: '#666'}} {...props} />,
                ul: ({node, ...props}) => <ul style={{paddingLeft: '20px', marginBottom: '12px'}} {...props} />,
                ol: ({node, ...props}) => <ol style={{paddingLeft: '20px', marginBottom: '12px'}} {...props} />,
                li: ({node, ...props}) => <li style={{marginBottom: '4px', lineHeight: '1.6'}} {...props} />,
                // GFM表格样式优化
                table: ({node, ...props}) => (
                  <div style={{overflowX: 'auto', marginBottom: '16px'}}>
                    <table style={{
                      borderCollapse: 'collapse', 
                      width: '100%', 
                      border: '1px solid #d0d7de',
                      fontSize: '14px'
                    }} {...props} />
                  </div>
                ),
                thead: ({node, ...props}) => <thead style={{backgroundColor: '#f6f8fa'}} {...props} />,
                tbody: ({node, ...props}) => <tbody {...props} />,
                tr: ({node, ...props}) => <tr style={{borderTop: '1px solid #d0d7de'}} {...props} />,
                th: ({node, ...props}) => (
                  <th style={{
                    border: '1px solid #d0d7de', 
                    padding: '6px 13px', 
                    backgroundColor: '#f6f8fa', 
                    textAlign: 'left',
                    fontWeight: '600',
                    color: '#24292f'
                  }} {...props} />
                ),
                td: ({node, ...props}) => (
                  <td style={{
                    border: '1px solid #d0d7de', 
                    padding: '6px 13px',
                    color: '#24292f'
                  }} {...props} />
                ),
                // 删除线支持 (GFM)
                del: ({node, ...props}) => <del style={{textDecoration: 'line-through'}} {...props} />,
                // 强调样式
                strong: ({node, ...props}) => <strong style={{fontWeight: 'bold'}} {...props} />,
                em: ({node, ...props}) => <em style={{fontStyle: 'italic'}} {...props} />,
                // 链接样式
                a: ({node, ...props}) => <a style={{color: '#0969da', textDecoration: 'underline'}} {...props} />,
                // 分割线
                hr: ({node, ...props}) => <hr style={{border: 'none', borderTop: '1px solid #d0d7de', margin: '24px 0'}} {...props} />,
              }}
            >
              {textContent}
            </ReactMarkdown>
          </div>
        )}
        {!textLoading && !textError && !textContent && (
          <FileError>文件内容为空</FileError>
        )}
      </div>
    );
  }

  // Excel文件预览
  if (['xlsx', 'xls'].includes(fileExtension || '')) {
    return (
      <div className={styles.documentContainer}>
        <Excel filePath={url} />
      </div>
    );
  }

  // Word文档预览
  if (['docx', 'doc'].includes(fileExtension || '')) {
    return (
      <div className={styles.documentContainer}>
        <Docx filePath={url} />
      </div>
    );
  }

  // 原有的PDF处理逻辑
  return (
    <div className={styles.documentContainer}>
      <PdfLoader
        url={url}
        beforeLoad={<Skeleton active />}
        workerSrc="/pdfjs-dist/pdf.worker.min.js"
        errorMessage={<FileError>{error}</FileError>}
      >
        {(pdfDocument) => {
          pdfDocument.getPage(1).then((page) => {
            const viewport = page.getViewport({ scale: 1 });
            const width = viewport.width;
            const height = viewport.height;
            setWidthAndHeight(width, height);
          });

          return (
            <PdfHighlighter
              pdfDocument={pdfDocument}
              enableAreaSelection={(event) => event.altKey}
              onScrollChange={resetHash}
              scrollRef={(scrollTo) => {
                ref.current = scrollTo;
                setLoaded(true);
              }}
              onSelectionFinished={() => null}
              highlightTransform={(
                highlight,
                index,
                setTip,
                hideTip,
                viewportToScaled,
                screenshot,
                isScrolledTo,
              ) => {
                const isTextHighlight = !Boolean(
                  highlight.content && highlight.content.image,
                );

                const component = isTextHighlight ? (
                  <Highlight
                    isScrolledTo={isScrolledTo}
                    position={highlight.position}
                    comment={highlight.comment}
                  />
                ) : (
                  <AreaHighlight
                    isScrolledTo={isScrolledTo}
                    highlight={highlight}
                    onChange={() => {}}
                  />
                );

                return (
                  <Popup
                    popupContent={<HighlightPopup {...highlight} />}
                    onMouseOver={(popupContent) =>
                      setTip(highlight, () => popupContent)
                    }
                    onMouseOut={hideTip}
                    key={index}
                  >
                    {component}
                  </Popup>
                );
              }}
              highlights={state}
            />
          );
        }}
      </PdfLoader>
    </div>
  );
};

export default DocumentPreviewer;
