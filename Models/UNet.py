import torch
import torch.nn as nn
import torchvision.models as model
import torch.nn.functional as functional

class BasicConv2d(nn.Module):
    def __init__(self, 
                 in_channels, 
                 out_channels, 
                 kernel_size, 
                 stride, 
                 pad, 
                 if_Bn=True, 
                 activation=nn.ReLU(inplace=True)):
        super(BasicConv2d, self).__init__()
        self.conv2d = nn.Conv2d(in_channels, out_channels, kernel_size, stride=stride, padding=pad)
        self.if_Bn = if_Bn
        if self.if_Bn:
            self.Bn = nn.BatchNorm2d(out_channels)
        self.activation = activation
    
    def forward(self, x):
        x = self.conv2d(x)
        if self.if_Bn:
            x = self.Bn(x)
        x = self.activation(x)
        return x


class Encoder(nn.Module):
    def __init__(self, pretrain=True):
        super(Encoder, self).__init__()
        self.B1_C2 = nn.Sequential(*(list(list(model.vgg16_bn(pretrained=pretrain).children())[0].children())[0:6]))
        self.B2_C2 = nn.Sequential(*(list(list(model.vgg16_bn(pretrained=pretrain).children())[0].children())[6:13]))
        self.B3_C3 = nn.Sequential(*(list(list(model.vgg16_bn(pretrained=pretrain).children())[0].children())[13:23]))
        self.B4_C3 = nn.Sequential(*(list(list(model.vgg16_bn(pretrained=pretrain).children())[0].children())[23:33]))
        self.B5_C3 = nn.Sequential(*(list(list(model.vgg16_bn(pretrained=pretrain).children())[0].children())[33:43]))
        if pretrain == False:
            for m in self.modules():
                if isinstance(m, nn.Conv2d):
                    nn.init.normal_(m.weight, std=0.01)
                    if m.bias is not None:
                        nn.init.constant_(m.bias, 0)
                elif isinstance(m, nn.BatchNorm2d):
                    nn.init.constant_(m.weight, 1)
                    nn.init.constant_(m.bias, 0)
    
    def forward(self, x):
        B1_C2_output = self.B1_C2(x)
        B2_C2_output = self.B2_C2(B1_C2_output)
        B3_C3_output = self.B3_C3(B2_C2_output)
        B4_C3_output = self.B4_C3(B3_C3_output)
        B5_C3_output = self.B5_C3(B4_C3_output)
        return B5_C3_output, B4_C3_output, B3_C3_output,  B2_C2_output

class Decoder(nn.Module):
    def __init__(self):
        super(Decoder, self).__init__()
        self.Reinforcement_Branch_Block_1 = nn.Sequential(
            BasicConv2d(1024, 256, 1, 1, 0),
            BasicConv2d(256, 256, 3, 1, 1)
        )
        
        self.Reinforcement_Branch_Block_2 = nn.Sequential(
            BasicConv2d(512, 128, 1, 1, 0),
            BasicConv2d(128, 128, 3, 1, 1)
        )
        
        self.Reinforcement_Branch_Block_3 = nn.Sequential(
            BasicConv2d(256, 64, 1, 1, 0),
            BasicConv2d(64, 64, 3, 1, 1),
            BasicConv2d(64, 32, 3, 1, 1, if_Bn=False),
            nn.Conv2d(32, 1, 1, 1, 0),
        )
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.normal_(m.weight, std=0.01)
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)
                
    def forward(self, B5_C3, B4_C3, B3_C3, B2_C2):
        concat_1 = torch.cat(
                [functional.interpolate(B5_C3, scale_factor=[2, 2, 1], mode="nearest"), B4_C3], dim=1)
        concat_2 = torch.cat(
                [functional.interpolate(self.Reinforcement_Branch_Block_1(concat_1), scale_factor=[2, 2, 1], mode="nearest"), B3_C3], 
                dim=1
            )
        concat_3 = torch.cat(
                [functional.interpolate(self.Reinforcement_Branch_Block_2(concat_2), scale_factor=[2, 2, 1], mode="nearest"), B2_C2], dim=1)
        return self.Reinforcement_Branch_Block_3(concat_3)
        
        
class UNet(nn.Module):
    def __init__(self, pretrain=True):
        super(UNet, self).__init__()
        self.encoder = Encoder(pretrain)
        self.decoder = Decoder()
        self.output_layer = nn.Sigmoid()
        for m in self.output_layer.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.normal_(m.weight, std=0.01)
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)
        
    def forward(self, x):
        B5_C3, B4_C3, B3_C3, B2_C2 = self.encoder(x)
        decoder_out = self.decoder(B5_C3, B4_C3, B3_C3, B2_C2)
        return self.output_layer(decoder_out)
        
