import { Images } from '@/constants/common';
import { api_host } from '@/utils/api';
import { Flex, Spin } from 'antd';
import { useParams, useSearchParams } from 'umi';
import { useEffect, useState } from 'react';
import { Authorization } from '@/constants/authorization';
import { getAuthorization } from '@/utils/authorization-util';
import Docx from './docx';
import Excel from './excel';
import Image from './image';
import Pdf from './pdf';
import FileError from './file-error';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { previewHtmlFile } from '@/utils/file-util';
import styles from './index.less';

// TODO: The interface returns an incorrect content-type for the SVG.

const DocumentViewer = () => {
  const { id: documentId } = useParams();
  const [currentQueryParameters] = useSearchParams();
  const ext = currentQueryParameters.get('ext');
  const prefix = currentQueryParameters.get('prefix');
  const api = `${api_host}/${prefix || 'file'}/get/${documentId}`;

  // State for text file handling
  const [textContent, setTextContent] = useState<string>('');
  const [textLoading, setTextLoading] = useState(false);
  const [textError, setTextError] = useState<string>('');

  // 处理文本文件（txt, md）
  useEffect(() => {
    if ((ext === 'txt' || ext === 'md') && api) {
      const fetchTextContent = async () => {
        try {
          setTextLoading(true);
          setTextError('');

          const response = await fetch(api, {
            headers: {
              [Authorization]: getAuthorization(),
            },
          });

          if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
          }

          const text = await response.text();
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
  }, [api, ext]);

  if (ext === 'html' && documentId) {
    previewHtmlFile(documentId);
    return null;
  }

  return (
    <section className={styles.viewerWrapper} style={{ height: '100vh', overflow: 'hidden' }}>
      {Images.includes(ext!) && (
        <Flex className={styles.image} align="center" justify="center">
          <Image src={api} preview={false}></Image>
        </Flex>
      )}
      {ext === 'pdf' && <Pdf url={api}></Pdf>}
      {(ext === 'xlsx' || ext === 'xls') && <Excel filePath={api}></Excel>}
      {ext === 'docx' && <Docx filePath={api}></Docx>}
      {ext === 'txt' && (
        <div style={{ 
          width: '100%', 
          height: '100%', 
          position: 'relative'
        }}>
          {textLoading && (
            <Flex justify="center" align="center" style={{ height: '200px' }}>
              <Spin size="large" />
            </Flex>
          )}
          {textError && <FileError>{textError}</FileError>}
          {!textLoading && !textError && textContent && (
            <div style={{ 
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              padding: '20px', 
              overflow: 'auto',
              backgroundColor: '#fff'
            }}>
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
                overflowWrap: 'break-word'
              }}>
                {textContent}
              </pre>
            </div>
          )}
          {!textLoading && !textError && !textContent && (
            <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <FileError>文件内容为空</FileError>
            </div>
          )}
        </div>
      )}
      {ext === 'md' && (
        <div style={{ 
          width: '100%', 
          height: '100%', 
          position: 'relative'
        }}>
          {textLoading && (
            <Flex justify="center" align="center" style={{ height: '200px' }}>
              <Spin size="large" />
            </Flex>
          )}
          {textError && <FileError>{textError}</FileError>}
          {!textLoading && !textError && textContent && (
            <div style={{ 
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              padding: '20px', 
              overflow: 'auto',
              backgroundColor: '#fff'
            }}>
              <div style={{
                width: '100%',
                maxWidth: '100%',
                height: 'auto',
                padding: '16px',
                margin: 0,
                backgroundColor: '#ffffff',
                border: '1px solid #d9d9d9',
                borderRadius: '6px'
              }}>
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    h1: (props) => <h1 style={{color: '#262626', fontSize: '24px', marginBottom: '16px', fontWeight: 'bold'}} {...props} />,
                    h2: (props) => <h2 style={{color: '#262626', fontSize: '20px', marginBottom: '14px', fontWeight: 'bold'}} {...props} />,
                    h3: (props) => <h3 style={{color: '#262626', fontSize: '18px', marginBottom: '12px', fontWeight: 'bold'}} {...props} />,
                    h4: (props) => <h4 style={{color: '#262626', fontSize: '16px', marginBottom: '10px', fontWeight: 'bold'}} {...props} />,
                    p: (props) => <p style={{color: '#262626', lineHeight: '1.6', marginBottom: '12px'}} {...props} />,
                    code: (props) => {
                      const isInline = !props.className?.includes('language-');
                      return isInline ? 
                        <code style={{backgroundColor: '#f5f5f5', padding: '2px 4px', borderRadius: '4px', fontFamily: 'Monaco, Consolas, monospace', fontSize: '13px', color: '#e53e3e'}} {...props} /> :
                        <code style={{backgroundColor: '#f5f5f5', padding: '12px', borderRadius: '6px', display: 'block', fontFamily: 'Monaco, Consolas, monospace', fontSize: '13px', overflow: 'auto', lineHeight: '1.5'}} {...props} />;
                    },
                    pre: (props) => <pre style={{backgroundColor: '#f5f5f5', padding: '12px', borderRadius: '6px', overflow: 'auto', marginBottom: '16px'}} {...props} />,
                    table: (props) => (
                      <div style={{overflowX: 'auto', marginBottom: '16px'}}>
                        <table style={{
                          borderCollapse: 'collapse', 
                          width: '100%', 
                          border: '1px solid #d0d7de',
                          fontSize: '14px'
                        }} {...props} />
                      </div>
                    ),
                    thead: (props) => <thead style={{backgroundColor: '#f6f8fa'}} {...props} />,
                    tr: (props) => <tr style={{borderTop: '1px solid #d0d7de'}} {...props} />,
                    th: (props) => (
                      <th style={{
                        border: '1px solid #d0d7de', 
                        padding: '6px 13px', 
                        backgroundColor: '#f6f8fa', 
                        textAlign: 'left',
                        fontWeight: '600',
                        color: '#24292f'
                      }} {...props} />
                    ),
                    td: (props) => (
                      <td style={{
                        border: '1px solid #d0d7de', 
                        padding: '6px 13px',
                        color: '#24292f'
                      }} {...props} />
                    ),
                    blockquote: (props) => <blockquote style={{borderLeft: '4px solid #d9d9d9', paddingLeft: '16px', margin: '16px 0', fontStyle: 'italic', color: '#666'}} {...props} />,
                    ul: (props) => <ul style={{paddingLeft: '20px', marginBottom: '12px'}} {...props} />,
                    ol: (props) => <ol style={{paddingLeft: '20px', marginBottom: '12px'}} {...props} />,
                    li: (props) => <li style={{marginBottom: '4px', lineHeight: '1.6'}} {...props} />,
                    a: (props) => <a style={{color: '#0969da', textDecoration: 'underline'}} {...props} />,
                    hr: (props) => <hr style={{border: 'none', borderTop: '1px solid #d0d7de', margin: '24px 0'}} {...props} />,
                  }}
                >
                  {textContent}
                </ReactMarkdown>
              </div>
            </div>
          )}
          {!textLoading && !textError && !textContent && (
            <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <FileError>文件内容为空</FileError>
            </div>
          )}
        </div>
      )}
    </section>
  );
};

export default DocumentViewer;
