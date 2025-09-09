const express = require('express');
require('dotenv').config();
const nodemailer = require('nodemailer');
const cors = require('cors');
const app = express();
const port = 5000;
const { createLogger, format, transports } = require('winston');

const logger = createLogger({
  level: process.env.NODE_ENV === 'production' ? 'error' : 'debug',
  format: format.combine(
    format.timestamp(),
    format.json()
  ),
  transports: [
    new transports.Console(),
    new transports.File({ filename: 'logs/server.log' })
  ]
});

// Create nodemailer transporter for cPanel email
const createTransporter = () => {
  const port = parseInt(process.env.CPANEL_SMTP_PORT) || 465;
  const config = {
    host: process.env.CPANEL_SMTP_HOST,
    port: port,
    secure: port === 465, // true for 465 (SSL), false for 587 (TLS)
    auth: {
      user: process.env.CPANEL_EMAIL_USER,
      pass: process.env.CPANEL_EMAIL_PASS,
    },
    tls: {
      rejectUnauthorized: false
    }
  };
  
  return nodemailer.createTransport(config);
};

app.use(cors({
  origin: [
    'http://localhost:3000',
    'http://192.168.1.49:8081',
    'exp://192.168.1.49:8081',
    'https://bititecsystem.web.app'  
  ],
  methods: ['GET','POST', 'OPTIONS'],
  allowedHeaders: ['Content-Type']
}));

app.use(express.json());

app.post('/send-email', async (req, res) => {
  try {
    const { email, body, subject } = req.body;
    
    if (!email || !body) {
      return res.status(400).json({
        success: false,
        error: 'Email and body are required'
      });
    }
    
    const transporter = createTransporter();
    
    const mailOptions = {
      from: `"Bititec Systems" <${process.env.CPANEL_EMAIL_USER}>`,
      to: email,
      cc: process.env.CPANEL_CC_USER || '',
      subject: subject || 'Message from Bititec Systems',
      text: body,
      html: `<p>${body}</p>`,
    };
    
    await transporter.sendMail(mailOptions);
    res.json({ success: true });
  } catch (error) {
    logger.error('Email send error:', error);
    
    res.status(500).json({
      success: false,
      error: error.message,
      details: error.code || null
    });
  }
});

// Service call endpoint with cPanel SMTP 
app.post('/send-service-call', async (req, res) => {
  try {
    const { email, serviceCallId, tokenId, serviceCallInfo, expirationTime } = req.body;
    
    if (!email || !serviceCallId || !tokenId || !serviceCallInfo) {
      return res.status(400).json({
        success: false,
        error: 'Email, serviceCallId, tokenId, and serviceCallInfo are required'
      });
    }
    
    const expiresAt = expirationTime ? new Date(expirationTime).toLocaleString() : '1 hour from now';
    const ticketNo = serviceCallInfo.ticket_no || 'Unknown Ticket';
    const clientName = serviceCallInfo.client?.client_name || serviceCallInfo.client_name ||'Unknown Client';
    const clientLocation = serviceCallInfo.client?.client_location|| serviceCallInfo.client_location ||'Unknown Client';
    
    const baseUrl = process.env.FRONTEND_URL || 'https://bititecsystem.web.app';
    const serviceCallLink = `${baseUrl}/customer-service-call/${serviceCallId}?token=${tokenId}`;
    
    const subject = `Service Call Details: ${ticketNo} for ${clientName}, ${clientLocation}`;
    
    const htmlBody = `
      <div style="font-family: Arial, sans-serif; padding: 20px; max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 5px;">
        <h2 style="color: #4a4a4a; border-bottom: 1px solid #e0e0e0; padding-bottom: 10px;">Service Call Information</h2>
        
        <p>Hello,</p>
        
        <p>You have been given access to view service call details for ticket <strong>${ticketNo}</strong>.</p>
        
        <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0;">
          <p><strong>Client:</strong> ${clientName}, ${clientLocation}</p>
          <p><strong>Ticket Number:</strong> ${ticketNo}</p>
          <p><strong>Status:</strong> ${serviceCallInfo.status || 'N/A'}</p>
        </div>
        
        <p>To view the complete service call details, click the button below:</p>
        
        <div style="text-align: center; margin: 25px 0;">
          <a href="${serviceCallLink}" style="background-color: #1976d2; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; font-weight: bold;">View Service Call</a>
        </div>
        
        <p style="color: #757575; font-size: 0.9em;"><strong>Important:</strong> This link will expire on ${expiresAt}. Please access it before then.</p>
        
        <p>Thank you,<br />Bititec Systems Team</p>
      </div>
    `;
    
    const textBody = `
      Service Call Information
      
      Hello,
      
      You have been given access to view service call details for ticket ${ticketNo}.
      
      Client: ${clientName} 
      Ticket Number: ${ticketNo}
      Status: ${serviceCallInfo.status || 'N/A'}
      
      To view the complete service call details, visit this link:
      ${serviceCallLink}
      
      Important: This link will expire on ${expiresAt}. Please access it before then.
      
      Thank you,
      Bititec Systems Team
    `;
    
    const transporter = createTransporter();
    
    const mailOptions = {
      from: `"Bititec Systems" <${process.env.CPANEL_EMAIL_USER}>`,
      to: email,
      subject: subject,
      text: textBody,
      html: htmlBody,
    };
    
    await transporter.sendMail(mailOptions);
    res.json({ success: true });
  } catch (error) {
    logger.error('Service call email error:', error);
    
    res.status(500).json({
      success: false,
      error: error.message,
      details: error.code || null
    });
  }
});

// Quotation endpoint with cPanel SMTP
app.post('/send-quotation', async (req, res) => {
  try {
    const { email, quotationData } = req.body;
    
    if (!email || !quotationData) {
      return res.status(400).json({
        success: false,
        error: 'Email and quotation data are required'
      });
    }
    
    const {
      quotation_no,
      client_name,
      client_location,
      total_amount,
      valid_until,
      items = []
    } = quotationData;
    
    const subject = `Sales Quotation - ${quotation_no || 'New Quotation'}`;
    
    const itemsList = items.map(item => {
      const unitPrice = item.unit_price ? Number(item.unit_price) : 0;
      const totalPrice = item.total_price ? Number(item.total_price) : 0;
      
      return `<tr>
        <td style="padding: 8px; border: 1px solid #ddd;">${item.item_name}</td>
        <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">${item.quantity}</td>
        <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">KES ${unitPrice.toFixed(2)}</td>
        <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">KES ${totalPrice.toFixed(2)}</td>
      </tr>`;
    }).join('');
    
    const htmlBody = `
      <div style="font-family: Arial, sans-serif; padding: 20px; max-width: 700px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 5px;">
        <div style="text-align: center; margin-bottom: 30px;">
          <h1 style="color: #1976d2; margin: 0;">BITITEC SYSTEMS</h1>
          <p style="color: #666; margin: 5px 0;">Your Technology Partner</p>
        </div>
        
        <h2 style="color: #333; border-bottom: 2px solid #1976d2; padding-bottom: 10px;">Sales Quotation</h2>
        
        <p>Dear ${client_name},</p>
        
        <p>Kindly find the attached as requested and confirm receipt.</p>
        
        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
          <p><strong>Quotation Number:</strong> ${quotation_no || 'Pending'}</p>
          <p><strong>Client:</strong> ${client_name}, ${client_location}</p>
          <p><strong>Valid Until:</strong> ${valid_until ? new Date(valid_until).toLocaleDateString() : 'N/A'}</p>
          <p><strong>Total Amount:</strong> KES ${total_amount?.toFixed(2) || '0.00'}</p>
        </div>
        
        ${items.length > 0 ? `
        <h3 style="color: #333; margin-top: 25px;">Quotation Summary</h3>
        <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
          <thead>
            <tr style="background-color: #1976d2; color: white;">
              <th style="padding: 10px; border: 1px solid #ddd; text-align: left;">Item</th>
              <th style="padding: 10px; border: 1px solid #ddd; text-align: center;">Qty</th>
              <th style="padding: 10px; border: 1px solid #ddd; text-align: right;">Unit Price</th>
              <th style="padding: 10px; border: 1px solid #ddd; text-align: right;">Total</th>
            </tr>
          </thead>
          <tbody>
            ${itemsList}
          </tbody>
        </table>
        ` : ''}
        
        <div style="text-align: center; margin: 30px 0;">
          <p style="color: #666;">For any questions or clarifications, please don't hesitate to contact us.</p>
        </div>
        
        <div style="border-top: 1px solid #e0e0e0; padding-top: 20px; margin-top: 30px;">
          <p style="margin: 5px 0;">Good day.</p>
          <p style="margin: 5px 0;">Regards,</p>
          <p style="margin: 5px 0; font-weight: bold; color: #1976d2;">Faith Mutuku</p>
          <p style="margin: 5px 0; font-weight: bold; color: #1976d2;">Sales Executive</p>
          <p style="margin: 5px 0;">Tel: (+254)717-063-633</p>
          <p style="margin: 5px 0;">Email: sales@bititecsystems.com</p>
        </div>
      </div>
    `;
    
    const textBody = `
      BITITEC SYSTEMS - Sales Quotation
      
      Dear ${client_name},
      
      Kindly find the attached as requested and confirm receipt.
      
      Quotation Details:
      - Quotation Number: ${quotation_no || 'Pending'}
      - Client: ${client_name}, ${client_location}
      - Valid Until: ${valid_until ? new Date(valid_until).toLocaleDateString() : 'N/A'}
      - Total Amount: KES ${total_amount?.toFixed(2) || '0.00'}
      
      ${items.length > 0 ? `
      Items:
      ${items.map(item => `- ${item.item_name} (Qty: ${item.quantity}) - KES ${item.total_price?.toFixed(2) || '0.00'}`).join('\n')}
      ` : ''}
      
      For any questions or clarifications, please don't hesitate to contact us.
      
      Good day.
      
      Regards,
      Faith Mutuku
      Sales Executive
      Tel: (+254)717-063-633
      Email: sales@bititecsystems.com
    `;
    
    const transporter = createTransporter();
    
    const mailOptions = {
      from: `"Bititec Systems Sales" <sales@bititecsystems.com>`,
      to: email,
      subject: subject,
      text: textBody,
      html: htmlBody,
    };
    
    await transporter.sendMail(mailOptions);
    res.json({ success: true });
  } catch (error) {
    logger.error('Quotation email send error:', error);
    
    res.status(500).json({
      success: false,
      error: error.message,
      details: error.code || null
    });
  }
});

app.get('/health', (req, res) => {
  res.json({ status: 'ok' });
});

app.listen(port, '0.0.0.0', () => {
  logger.debug(`Email server running at http://localhost:${port}`);
});