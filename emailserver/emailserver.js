const express = require('express');
require('dotenv').config();
const sgMail = require('@sendgrid/mail');
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

sgMail.setApiKey(process.env.SENDGRID_API_KEY);

app.use(cors({
  origin: [
    'http://localhost:3000',
    'http://192.168.1.49:8081', // Your Expo Go URL
    'exp://192.168.1.49:8081'  // Alternative Expo URL format
  ],
  methods: ['POST'],
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
    
    const msg = {
      to: email,
      from: 'noreply@bititecsystems.com', 
      subject: subject || 'Message from Bititec Systems',
      text: body,
      html: `<p>${body}</p>`,
    };
    
    await sgMail.send(msg);
    res.json({ success: true });
  } catch (error) {
    logger.error(...args);
    
    if (error.response) {
      logger.error(...args);
    }
    
    res.status(500).json({
      success: false,
      error: error.message,
      details: error.response?.body?.errors || null
    });
  }
});

// New endpoint for sending service call links
app.post('/send-service-call', async (req, res) => {
  try {
    const { email, serviceCallId, tokenId, serviceCallInfo, expirationTime } = req.body;
    
    if (!email || !serviceCallId || !tokenId || !serviceCallInfo) {
      return res.status(400).json({
        success: false,
        error: 'Email, serviceCallId, tokenId, and serviceCallInfo are required'
      });
    }
    
    // Format the expiration time - convert to user-friendly format
    const expiresAt = expirationTime ? new Date(expirationTime).toLocaleString() : '1 hour from now';
    
    // Format ticket number and client name for subject line
    const ticketNo = serviceCallInfo.ticket_no || 'Unknown Ticket';
    const clientName = serviceCallInfo.client?.client_name || serviceCallInfo.client_name ||'Unknown Client';
    const clientLocation = serviceCallInfo.client?.client_location|| serviceCallInfo.client_location ||'Unknown Client';
    
    // Generate the access link
    // Frontend URL should match your React app URL
    const serviceCallLink = `http://localhost:3000/customer-service-call/${serviceCallId}?token=${tokenId}`;
    
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
    
    const msg = {
      to: email,
      from: 'noreply@bititecsystems.com',
      subject: subject,
      text: textBody,
      html: htmlBody,
    };
    
    await sgMail.send(msg);
    res.json({ success: true });
  } catch (error) {
    logger.error(error.message, { error });
    
    if (error.response) {
      logger.error(error.message, { error });
    }
    
    res.status(500).json({
      success: false,
      error: error.message,
      details: error.response?.body?.errors || null
    });
  }
});

app.listen(port, () => {
  logger.debug(`Email server running at http://localhost:${port}`);
});